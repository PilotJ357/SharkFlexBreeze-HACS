#!/usr/bin/env bash
# Decode fan remote packets from saved .cu8 IQ files or live SDR.
# Uses flex decoder built from identified timing parameters.
#
# Usage:
#   ./decode.sh <session_name>        # decode from saved .cu8 files
#   ./decode.sh live [session_name]   # live decode from SDR

set -euo pipefail

MODE="${1:-}"
SESSION="${2:-live_$(date +%Y%m%d_%H%M%S)}"
OUTDIR="$(dirname "$0")/captures"
FREQ="433.92M"
GAIN="49.6"

if ! command -v rtl_433 &>/dev/null; then
    echo "ERROR: rtl_433 not found"
    exit 1
fi

# OOK PWM flex decoder parameters derived from pulse analysis:
#   y = sync pulse (~4224us)
#   s = short/0 pulse (~308us)
#   l = long/1 pulse (~888us)
#   g = inter-symbol gap (~292us)
#   r = reset gap — using 9000us so each packet repetition decodes separately
#   t = tolerance (±80us)
# g removed — gap limit was fragmenting packets (intra-packet gaps vary 292–1752us)
# r=9000 — each ~9ms inter-repetition gap starts a new decode
# t=150 — generous tolerance (±150us) since we're estimating from histogram averages
FLEX="n=fan_remote,m=OOK_PWM,s=308,l=888,r=9000,t=150,y=4224"

if [ "$MODE" = "live" ]; then
    JSONLOG="$OUTDIR/${SESSION}.json"
    mkdir -p "$OUTDIR"
    echo "Live decoding at $FREQ gain=$GAIN"
    echo "Press buttons. Ctrl+C to stop."
    echo "JSON -> $JSONLOG"
    rtl_433 \
        -f "$FREQ" \
        -g "$GAIN" \
        -R 0 \
        -X "$FLEX" \
        -F kv \
        -F "json:$JSONLOG" \
        -M time -M level \
        2>&1 | tee "$OUTDIR/${SESSION}_decode.log"
else
    # Decode from saved .cu8 files
    SIGDIR="$OUTDIR/${MODE}_signals"
    if [ ! -d "$SIGDIR" ]; then
        echo "ERROR: $SIGDIR not found"
        echo "Usage: ./decode.sh <session_name>  or  ./decode.sh live [name]"
        exit 1
    fi

    CU8_FILES=("$SIGDIR"/*.cu8)
    if [ ${#CU8_FILES[@]} -eq 0 ] || [ ! -f "${CU8_FILES[0]}" ]; then
        echo "ERROR: No .cu8 files in $SIGDIR"
        exit 1
    fi

    JSONLOG="$OUTDIR/${MODE}_decoded.json"
    > "$JSONLOG"   # clear/create

    echo "Decoding ${#CU8_FILES[@]} saved signal file(s) from $SIGDIR"
    echo ""

    for f in "$SIGDIR"/*.cu8; do
        echo "--- $f"
        rtl_433 \
            -r "$f" \
            -X "$FLEX" \
            -F "json:$JSONLOG" \
            -M time -M level \
            2>&1
    done

    echo ""
    echo "Decoded packets -> $JSONLOG"
    echo ""
    echo "Decoded bit strings:"
    python3 - "$JSONLOG" <<'PYEOF'
import json, sys
from collections import Counter

path = sys.argv[1]
codes = []
with open(path) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
            code = e.get("codes") or e.get("data") or e.get("code") or e.get("hex")
            if code:
                codes.append(str(code))
        except json.JSONDecodeError:
            pass

if not codes:
    print("No decoded packets found. Flex decoder params may need tuning.")
    print("Try: adjust s/l/y values ±50us in decode.sh FLEX variable")
else:
    counter = Counter(codes)
    print(f"  {len(codes)} total packets, {len(counter)} unique codes")
    for code, count in counter.most_common():
        print(f"  [{count:3d}x]  {code}")
PYEOF
fi
