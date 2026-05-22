#!/usr/bin/env bash
# Capture the RF fan ID from your SharkFlexBreeze remote.
#
# Requirements: rtl_433 + an RTL-SDR dongle connected to this computer
#   macOS:  brew install rtl_433
#   Linux:  sudo apt install rtl-433
#
# Usage: ./scripts/get_fan_id.sh [fan_name]
#   fan_name: optional label, e.g. "bedroom" or "living_room"

set -euo pipefail

FAN_NAME="${1:-my_fan}"
FREQ="433.92M"
GAIN="49.6"
FLEX="n=fan_remote,m=OOK_PWM,s=308,l=888,r=9000,t=150,y=4224"
KNOWN_IDS_FILE="$(dirname "$0")/known_ids.json"

# ── prereq check ─────────────────────────────────────────────────────────────
if ! command -v rtl_433 &>/dev/null; then
    echo ""
    echo "ERROR: rtl_433 not found."
    echo "  macOS : brew install rtl_433"
    echo "  Linux : sudo apt install rtl-433"
    echo ""
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found."
    exit 1
fi

# ── capture ───────────────────────────────────────────────────────────────────
echo ""
echo "SharkFlexBreeze Fan ID Capture"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Fan name : $FAN_NAME"
echo "Frequency: $FREQ"
echo ""
echo "Point the remote at the SDR dongle and press ANY button."
echo "Waiting for signal... (Ctrl+C to cancel)"
echo ""

FAN_ID=""

# Run rtl_433, pipe JSON to python, stop as soon as we get a clean 41-bit decode
FAN_ID=$(
    rtl_433 \
        -f "$FREQ" \
        -g "$GAIN" \
        -R 0 \
        -X "$FLEX" \
        -F json \
        -M time \
        2>/dev/null \
    | python3 - <<'PYEOF'
import sys, json

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        e = json.loads(line)
    except json.JSONDecodeError:
        continue
    for row in e.get("rows", []):
        length = row.get("len", 0)
        code   = row.get("data", "").lower().strip()
        if 39 <= length <= 43 and len(code) == 11:
            # Fan ID = first 6 hex chars (24 bits)
            print(code[:6])
            sys.stdout.flush()
            sys.exit(0)
PYEOF
)

if [ -z "$FAN_ID" ]; then
    echo "No signal captured. Check SDR connection and try again."
    exit 1
fi

# ── result ────────────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Fan ID captured: $FAN_ID"
echo ""
echo "  Use this ID when adding the device in Home Assistant."
echo ""

# ── save to known_ids.json ───────────────────────────────────────────────────
python3 - "$KNOWN_IDS_FILE" "$FAN_ID" "$FAN_NAME" <<'PYEOF'
import json, sys, pathlib
from datetime import datetime

path     = pathlib.Path(sys.argv[1])
fan_id   = sys.argv[2]
fan_name = sys.argv[3]

ids = []
if path.exists():
    try:
        ids = json.loads(path.read_text())
    except (json.JSONDecodeError, ValueError):
        ids = []

# Update existing entry or append
existing = next((e for e in ids if e["fan_id"] == fan_id), None)
if existing:
    existing["name"] = fan_name
    existing["updated"] = datetime.now().strftime("%Y-%m-%d")
    print(f"  Updated existing entry for {fan_id}")
else:
    ids.append({
        "fan_id":   fan_id,
        "name":     fan_name,
        "captured": datetime.now().strftime("%Y-%m-%d"),
    })
    print(f"  Saved to {path}")

path.write_text(json.dumps(ids, indent=2))
PYEOF

echo ""
