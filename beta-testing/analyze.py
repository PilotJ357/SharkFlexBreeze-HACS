#!/usr/bin/env python3
"""
Analyze rtl_433 captures to identify fan remote commands.

With -R 0 (unknown protocol mode), rtl_433 writes pulse timing to the console
log rather than JSON. This script parses BOTH.

Usage:
    python3 analyze.py <session_name>           # analyze one session
    python3 analyze.py <session1> <session2>    # diff two fans (find fan ID bits)
    python3 analyze.py --pulses <session_name>  # dump raw pulse timing only
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

CAPTURES_DIR = Path(__file__).parent / "captures"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_json_events(name: str) -> list[dict]:
    path = CAPTURES_DIR / f"{name}.json"
    if not path.exists():
        return []
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def load_pulse_bursts(name: str) -> list[dict]:
    """
    Parse rtl_433 -A pulse analysis from the console log.

    rtl_433 outputs blocks like:
        Detected OOK package ...
        Analyzing pulses...
        Total samples: 12345
        Pulse width distribution:
          [ 0] ...
        Gap width distribution:
          [ 0] ...
        Pulse period distribution:
          ...
        Level estimates [high, low]:  ...
        RSSI: ...
        Frequency offsets: ...

    We capture each block as a dict with the raw text + parsed timing hints.
    """
    path = CAPTURES_DIR / f"{name}_console.log"
    if not path.exists():
        return []

    bursts = []
    current: list[str] = []
    in_burst = False

    with open(path) as f:
        for line in f:
            if "Detected OOK package" in line or "Detected FSK package" in line:
                if current:
                    bursts.append(_parse_burst(current))
                current = [line.rstrip()]
                in_burst = True
            elif in_burst:
                if line.strip() == "" and len(current) > 5:
                    # blank line after enough content = end of block
                    bursts.append(_parse_burst(current))
                    current = []
                    in_burst = False
                else:
                    current.append(line.rstrip())

    if current:
        bursts.append(_parse_burst(current))

    return bursts


def _parse_burst(lines: list[str]) -> dict:
    text = "\n".join(lines)
    burst: dict = {"raw": text, "modulation": "OOK"}

    if "FSK" in lines[0]:
        burst["modulation"] = "FSK"

    # Extract pulse count
    m = re.search(r"Pulse width distribution.*?\n(.*?)\n", text, re.DOTALL)
    if m:
        burst["pulse_text"] = m.group(1)

    # Extract level estimates
    m = re.search(r"Level estimates \[high, low\]:\s+([\d]+),\s+([\d]+)", text)
    if m:
        burst["level_high"] = int(m.group(1))
        burst["level_low"] = int(m.group(2))

    # Extract RSSI
    m = re.search(r"RSSI:\s+([-\d.]+)", text)
    if m:
        burst["rssi"] = float(m.group(1))

    # Extract all pulse/gap timing numbers — format: "[ N] count:  X  width: Y us"
    pulse_widths = re.findall(r"Pulse width.*?(?=Gap width|$)", text, re.DOTALL)
    gap_widths = re.findall(r"Gap width.*?(?=Pulse period|Level|$)", text, re.DOTALL)

    def extract_widths(block: str) -> list[int]:
        return [int(x) for x in re.findall(r"width:\s+(\d+)\s+us", block)]

    if pulse_widths:
        burst["pulse_us"] = extract_widths(pulse_widths[0])
    if gap_widths:
        burst["gap_us"] = extract_widths(gap_widths[0])

    return burst


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def extract_codes(events: list[dict]) -> list[str]:
    codes = []
    for e in events:
        for field in ("data", "codes", "code", "raw_message", "hex_message"):
            if field in e and e[field]:
                codes.append(str(e[field]))
                break
        else:
            skip = {"time", "model", "mod", "freq", "freq1", "freq2",
                    "rssi", "snr", "noise", "id", "channel"}
            payload = {k: v for k, v in e.items() if k not in skip}
            if payload:
                codes.append(json.dumps(payload, sort_keys=True))
    return codes


def _is_clean_burst(b: dict) -> bool:
    """
    Heuristic: a real OOK remote burst has:
      - 1–5 distinct pulse widths in 100–50000us (1 = PPM/constant-pulse; sync can be long)
      - 1–6 distinct gap widths in 50–200000us
      - NOT 8+ distinct pulse widths (wideband noise signature)
    """
    p = b.get("pulse_us", [])
    g = b.get("gap_us", [])
    if not p or not g:
        return False
    p_real = [x for x in p if 100 <= x <= 50000]
    g_real = [x for x in g if 50 <= x <= 200000]
    return 1 <= len(p_real) <= 5 and 1 <= len(g_real) <= 6 and len(p) <= 8


def summarize_pulses(bursts: list[dict]):
    if not bursts:
        print("  No pulse bursts found in console log.")
        return

    print(f"\n  {len(bursts)} total signal burst(s) detected")

    clean = [b for b in bursts if _is_clean_burst(b)]
    noisy = len(bursts) - len(clean)
    print(f"  {len(clean)} look like clean OOK remote bursts  ({noisy} filtered as noise)\n")

    # Always show ALL burst timing — clean and noisy — so nothing is hidden
    timing_sigs_all = []
    for b in bursts:
        p = tuple(sorted(b.get("pulse_us", [])))
        g = tuple(sorted(b.get("gap_us", [])))
        is_c = b in clean
        timing_sigs_all.append((p, g, is_c))

    # Group by (p,g) signature
    sig_counter: Counter = Counter((p, g) for p, g, _ in timing_sigs_all)
    sig_clean = {(p, g) for p, g, c in timing_sigs_all if c}

    print(f"\n  All burst timing signatures [{len(sig_counter)} unique]  (✓ = passed clean filter):")
    for (p, g), count in sig_counter.most_common(15):
        marker = "✓" if (p, g) in sig_clean else " "
        print(f"  {marker} [{count:3d}x]  pulses={list(p)} us   gaps={list(g)} us")

    if not clean:
        print(f"\n  No bursts passed clean filter — printing most-repeated burst raw anyway:")
        best_sig = sig_counter.most_common(1)[0][0]
        for b in bursts:
            p = tuple(sorted(b.get("pulse_us", [])))
            g = tuple(sorted(b.get("gap_us", [])))
            if (p, g) == best_sig:
                print(b["raw"])
                break
        return

    # Print full -A block for most-repeated clean burst
    clean_counter: Counter = Counter(
        (tuple(sorted(b.get("pulse_us", []))), tuple(sorted(b.get("gap_us", []))))
        for b in clean
    )
    most_common_sig = clean_counter.most_common(1)[0][0]
    for b in clean:
        p = tuple(sorted(b.get("pulse_us", [])))
        g = tuple(sorted(b.get("gap_us", [])))
        if (p, g) == most_common_sig:
            print(f"\n  --- Most common clean burst ---")
            print(b["raw"])
            break


def analyze_session(name: str, pulses_only: bool = False):
    events = load_json_events(name)
    bursts = load_pulse_bursts(name)

    print(f"\n{'='*60}")
    print(f"Session: {name}")
    print(f"  JSON events : {len(events)}")
    print(f"  Pulse bursts: {len(bursts)}")
    print(f"{'='*60}")

    if pulses_only:
        summarize_pulses(bursts)
        return

    # JSON decoded events (only present if rtl_433 knows the protocol)
    if events:
        by_model = defaultdict(list)
        for e in events:
            by_model[e.get("model", "UNKNOWN")].append(e)

        for model, evts in by_model.items():
            codes = extract_codes(evts)
            counter = Counter(codes)
            print(f"\nDecoded — {model}  ({len(evts)} packets, {len(counter)} unique codes)")
            for code, count in counter.most_common(20):
                print(f"  [{count:3d}x]  {code}")
    else:
        print("\nNo JSON-decoded events (expected — unknown protocol with -R 0)")

    # Pulse analysis from console log
    print("\nPulse analysis (from -A output):")
    summarize_pulses(bursts)

    if bursts:
        print("\nNext step: identify short/long pulse ratio to determine encoding.")
        print("  PWM: 2 pulse widths + 1 gap  (e.g. short=300us, long=900us)")
        print("  PPM: 1 pulse width + 2 gap widths")
        print("  Manchester: equal pulse/gap widths, transitions encode bits")
        print("\nThen run with a flex decoder:")
        _suggest_flex(bursts)


def _suggest_flex(bursts: list[dict]):
    """Suggest a rtl_433 flex decoder based on observed timing."""
    # Find most common burst
    timing_sigs = []
    for b in bursts:
        p = tuple(sorted(b.get("pulse_us", [])))
        g = tuple(sorted(b.get("gap_us", [])))
        timing_sigs.append(((p, g), b))

    if not timing_sigs:
        return

    counter: Counter = Counter(t[0] for t in timing_sigs)
    best_sig = counter.most_common(1)[0][0]
    best_burst = next(b for sig, b in timing_sigs if sig == best_sig)

    p = list(best_burst.get("pulse_us", []))
    g = list(best_burst.get("gap_us", []))

    if len(p) >= 2 and len(g) >= 1:
        short_p = min(p)
        long_p = max(p)
        gap = g[0] if g else 1000
        reset = max(g) if g else 9000
        print(f"\n  Suggested flex decoder (adjust if needed):")
        print(f"  rtl_433 -f 433.87M -X 'n=fan,m=OOK_PWM,s={short_p},l={long_p},r={reset},g={gap},t=100'")


def diff_sessions(name1: str, name2: str):
    e1 = load_json_events(name1)
    e2 = load_json_events(name2)
    b1 = load_pulse_bursts(name1)
    b2 = load_pulse_bursts(name2)

    print(f"\n{'='*60}")
    print(f"Fan diff: {name1}  vs  {name2}")
    print(f"{'='*60}")

    codes1 = [c for c in extract_codes(e1) if _is_hex(c)]
    codes2 = [c for c in extract_codes(e2) if _is_hex(c)]

    if codes1 and codes2:
        _hex_diff(codes1, codes2, name1, name2)
    else:
        print(f"\nNo hex-decoded events in one or both sessions.")
        print(f"  {name1}: {len(b1)} pulse bursts")
        print(f"  {name2}: {len(b2)} pulse bursts")
        print("Need flex decoder first — run single-session analysis to get timing,")
        print("then add flex decoder and re-capture.")


def _is_hex(s: str) -> bool:
    s = s.replace("0x", "").replace(" ", "")
    return len(s) > 0 and all(c in "0123456789abcdefABCDEF" for c in s)


def _hex_diff(codes1: list[str], codes2: list[str], n1: str, n2: str):
    top1 = Counter(codes1).most_common(1)
    top2 = Counter(codes2).most_common(1)

    c1 = top1[0][0].replace("0x", "").replace(" ", "")
    c2 = top2[0][0].replace("0x", "").replace(" ", "")

    print(f"\n  {n1} dominant: {c1}  ({top1[0][1]}x)")
    print(f"  {n2} dominant: {c2}  ({top2[0][1]}x)")

    if len(c1) != len(c2):
        print(f"\n  WARNING: different lengths ({len(c1)} vs {len(c2)} hex chars). Can't bit-diff.")
        return

    try:
        b1 = bin(int(c1, 16))[2:].zfill(len(c1) * 4)
        b2 = bin(int(c2, 16))[2:].zfill(len(c2) * 4)
        diff = [i for i, (x, y) in enumerate(zip(b1, b2)) if x != y]
        same = [i for i in range(len(b1)) if i not in diff]

        print(f"\n  Binary {n1}: {b1}")
        print(f"  Binary {n2}: {b2}")
        print(f"\n  Differing bits ({len(diff)}): positions {diff}  ← FAN ID bits")
        print(f"  Identical bits ({len(same)}): likely command bits")

        if diff:
            mask = sum(1 << (len(b1) - 1 - i) for i in diff)
            print(f"\n  Fan ID bitmask : 0x{mask:0{len(c1)}X}")
            print(f"  {n1} ID value  : 0x{int(c1,16) & mask:0{len(c1)}X}")
            print(f"  {n2} ID value  : 0x{int(c2,16) & mask:0{len(c1)}X}")

    except ValueError as ex:
        print(f"  Parse error: {ex}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    pulses_only = "--pulses" in args
    args = [a for a in args if a != "--pulses"]

    if len(args) == 1:
        analyze_session(args[0], pulses_only=pulses_only)
    elif len(args) == 2:
        diff_sessions(args[0], args[1])
    else:
        print("Too many args. See usage.")
        sys.exit(1)
