#!/usr/bin/env python3
import sys, json, datetime

watch = sys.argv[1].lower().strip() if len(sys.argv) > 1 else "any"
watch_any = (watch in ("any", "all"))
press_count = 0
last_code = None
last_time = None
DEBOUNCE_S = 0.5

try:
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
            code = row.get("data", "").lower().strip()
            if not (39 <= length <= 43) or not code:
                continue

            now_ts = datetime.datetime.now().timestamp()
            is_match = watch_any or code == watch

            if not is_match:
                ts = datetime.datetime.now().strftime("%H:%M:%S")
                print(f"[{ts}]  UNKNOWN  len={length}  {code}", flush=True)
                continue

            if code == last_code and last_time and (now_ts - last_time) < DEBOUNCE_S:
                continue

            last_code = code
            last_time = now_ts
            press_count += 1
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            rssi = e.get("rssi", "?")
            print(f"[{ts}]  DETECTED #{press_count:03d}  {code}  RSSI:{rssi} dB", flush=True)

except KeyboardInterrupt:
    pass
