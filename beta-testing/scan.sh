#!/usr/bin/env bash
# Scan 300-440 MHz for the strongest signal while pressing remote buttons.
# Helps find the actual transmit frequency if Broadlink's reported freq is off.
#
# Usage: ./scan.sh [duration_seconds]
#   duration_seconds: how long to scan (default 30)
#
# Output: scan_results.csv  +  scan_results.txt (sorted by peak power)

set -euo pipefail

DURATION="${1:-30}"
OUTDIR="$(dirname "$0")/captures"
CSV="$OUTDIR/scan_results.csv"
TXT="$OUTDIR/scan_results.txt"

if ! command -v rtl_power &>/dev/null; then
    echo "ERROR: rtl_power not found (should be installed with rtl_433 / rtl-sdr)"
    exit 1
fi

mkdir -p "$OUTDIR"

echo "============================================"
echo "Scanning 300-440 MHz for ${DURATION}s"
echo "KEEP PRESSING THE REMOTE BUTTON REPEATEDLY"
echo "Output: $CSV"
echo "============================================"
echo ""

# Scan 300-440 MHz in 100kHz steps, 1s integration, for DURATION seconds
rtl_power -f 300M:440M:100k -g 49.6 -i 1 -e "${DURATION}s" "$CSV"

echo ""
echo "Scan complete. Finding peak frequencies..."

# Parse CSV and find top 20 strongest signals
# rtl_power CSV format: date, time, hz_low, hz_high, hz_step, samples, db...
python3 - "$CSV" "$TXT" <<'EOF'
import sys, csv
from collections import defaultdict

in_file = sys.argv[1]
out_file = sys.argv[2]

peaks = defaultdict(list)

with open(in_file) as f:
    for row in csv.reader(f):
        if len(row) < 7:
            continue
        try:
            hz_low  = float(row[2])
            hz_step = float(row[4])
            dbs     = [float(x) for x in row[6:] if x.strip()]
            for i, db in enumerate(dbs):
                freq_mhz = (hz_low + i * hz_step) / 1e6
                peaks[round(freq_mhz, 3)].append(db)
        except (ValueError, IndexError):
            continue

# Average power per frequency, sort descending
avg_power = {f: sum(v)/len(v) for f, v in peaks.items()}
sorted_peaks = sorted(avg_power.items(), key=lambda x: x[1], reverse=True)

lines = ["Top 30 frequencies by average power during scan:", ""]
for freq, pwr in sorted_peaks[:30]:
    lines.append(f"  {freq:8.3f} MHz   {pwr:+6.1f} dBm")

output = "\n".join(lines)
print(output)
with open(out_file, "w") as f:
    f.write(output + "\n")

print(f"\nFull results saved to {out_file}")
EOF
