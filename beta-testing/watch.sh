#!/usr/bin/env bash
# Watch for fan remote button presses and print a clear notification.
# Usage: ./watch.sh [known_code]
#   known_code: hex code to watch for (default: 0e37eeaa558)
#               pass "any" to alert on ANY 41-bit decode

WATCH_CODE="${1:-0e37eeaa558}"
FREQ="433.92M"
GAIN="49.6"
FLEX="n=fan_remote,m=OOK_PWM,s=308,l=888,r=9000,t=150,y=4224"

echo "========================================"
echo "Watching for: ${WATCH_CODE}"
echo "Freq: $FREQ  Gain: $GAIN"
echo "Press buttons. Ctrl+C to stop."
echo "========================================"
echo ""

rtl_433 \
    -f "$FREQ" \
    -g "$GAIN" \
    -R 0 \
    -X "$FLEX" \
    -F json \
    -M time \
    2>/dev/null \
| python3 "$(dirname "$0")/watch_parser.py" "$WATCH_CODE"
