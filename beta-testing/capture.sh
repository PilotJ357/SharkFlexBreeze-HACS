#!/usr/bin/env bash
# Capture RF signals from fan remotes using rtl_433
# Usage: ./capture.sh <session_name> [frequency_MHz] [duration_seconds]
#   session_name: e.g. "fan1_power_on", "fan2_speed_high"
#   frequency_MHz: default 433.87 (Broadlink-confirmed freq for this fan)
#   duration_seconds: default 0 (run until Ctrl+C)

set -euo pipefail

SESSION="${1:-test_$(date +%Y%m%d_%H%M%S)}"
FREQ="${2:-433.87}M"
DURATION="${3:-0}"
GAIN="${4:-40}"   # dB — try 40, then 49.6 (max), then 0 (auto)
OUTDIR="$(dirname "$0")/captures"
JSONLOG="$OUTDIR/${SESSION}.json"
SIGDIR="$OUTDIR/${SESSION}_signals"
CONSOLELOG="$OUTDIR/${SESSION}_console.log"

if ! command -v rtl_433 &>/dev/null; then
    echo "ERROR: rtl_433 not found. Install with: brew install rtl_433"
    exit 1
fi

mkdir -p "$OUTDIR" "$SIGDIR"

echo "=========================================="
echo "Session  : $SESSION"
echo "Frequency: $FREQ"
echo "Gain     : ${GAIN} dB  (try 40, 49.6, or 0=auto)"
echo "JSON log : $JSONLOG"
echo "Signals  : $SIGDIR/"
echo "Console  : $CONSOLELOG"
echo "Duration : ${DURATION}s (0 = until Ctrl+C)"
echo "=========================================="
echo ""
echo "Press buttons NOW. Ctrl+C to stop."
echo ""

DURATION_FLAG=""
if [ "$DURATION" -gt 0 ] 2>/dev/null; then
    DURATION_FLAG="-T $DURATION"
fi

# -R 0       disable ALL built-in decoders (avoids false positives from weather sensors etc.)
# -A         pulse analysis — prints timing for every detected burst; this is how we reverse
#            an unknown protocol. Output goes to console/log, NOT json.
# -F json    decoded events to JSON (will be empty if protocol is truly unknown, but keeps
#            the file ready for when we add a flex decoder later)
# -S all     save every signal burst as a raw .cu8 IQ file in SIGDIR for offline re-analysis
# -M time/level/protocol  enrich any decoded events with metadata
rtl_433 \
    -f "$FREQ" \
    -g "$GAIN" \
    -R 0 \
    -A \
    -F "json:$JSONLOG" \
    -S all \
    -M time \
    -M level \
    -M protocol \
    ${DURATION_FLAG} \
    2>&1 | tee "$CONSOLELOG"

echo ""
echo "Pulse analysis -> $CONSOLELOG"
echo "Raw IQ files   -> $SIGDIR/"
echo ""
echo "Next steps:"
echo "  1. python3 analyze.py $SESSION          # parse pulse timing from console log"
echo "  2. Once timing known, add flex decoder and re-run on saved IQ files"
