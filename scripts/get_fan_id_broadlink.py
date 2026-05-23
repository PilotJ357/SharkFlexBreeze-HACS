#!/usr/bin/env python3
"""
Capture a Shark Flex Breeze fan ID using a Broadlink RM4 Pro (or compatible device).

Usage:
    python3 get_fan_id_broadlink.py <broadlink-ip>

Requirements:
    pip3 install broadlink

The script sweeps for the remote's frequency, captures one RF packet,
and decodes the 24-bit fan ID embedded in the transmission.
"""
import sys
import time

try:
    import broadlink
except ImportError:
    print("Error: broadlink library not installed. Run: pip3 install broadlink")
    sys.exit(1)

_TICK_US = 32.84
_LONG_THRESHOLD_US = 600  # above = LONG pulse (bit 0), below = SHORT pulse (bit 1)
_PACKET_BITS = 41
_FAN_ID_BITS = 24


def _decode_b1_timings(data: bytes) -> list[int]:
    if len(data) < 8:
        return []
    timings, i, high = [], 8, True
    while i < len(data):
        if data[i] == 0x00 and i + 2 < len(data):
            ticks = (data[i + 1] << 8) | data[i + 2]
            i += 3
        else:
            ticks = data[i]
            i += 1
        us = round(ticks * _TICK_US)
        timings.append(us if high else -us)
        high = not high
    return timings


def _extract_fan_id(timings: list[int]) -> str | None:
    # Skip sync pulse and post-sync reset gap
    if len(timings) < 2 + _FAN_ID_BITS * 2:
        return None
    bits = []
    i = 2  # skip sync + reset gap
    while len(bits) < _FAN_ID_BITS and i + 1 < len(timings):
        pulse = timings[i]
        bits.append("0" if pulse >= _LONG_THRESHOLD_US else "1")
        i += 2
    if len(bits) < _FAN_ID_BITS:
        return None
    return hex(int("".join(bits), 2))[2:].zfill(6)


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: python3 {sys.argv[0]} <broadlink-ip>")
        sys.exit(1)

    ip = sys.argv[1]
    print(f"Connecting to Broadlink at {ip}...")
    try:
        dev = broadlink.hello(ip)
        dev.auth()
    except Exception as e:
        print(f"Error: could not connect — {e}")
        sys.exit(1)
    print(f"Connected: {dev.model} (0x{dev.devtype:04x})\n")

    print("STEP 1: Hold the fan remote within 2 inches of the Broadlink.")
    print("        Hold down any button CONTINUOUSLY until you see 'FOUND'.")
    input("\nPress Enter, then hold the button...\n")

    dev.sweep_frequency()
    found, freq = False, 0.0
    for i in range(30):
        time.sleep(1)
        found, freq = dev.check_frequency()
        print(f"  [{i + 1:2d}s] {freq} MHz {'<-- FOUND!' if found else ''}")
        if found:
            break

    if not found:
        dev.cancel_sweep_frequency()
        print("\nNo frequency detected. Hold the button more firmly and try again.")
        sys.exit(1)

    print(f"\nLocked at {freq:.3f} MHz. Release the button.\n")

    print("STEP 2: Press any button on the remote ONCE quickly.")
    input("Press Enter, then press the button...\n")

    dev.find_rf_packet()
    data = None
    for i in range(15):
        time.sleep(1)
        try:
            data = dev.check_data()
            if data:
                break
        except Exception:
            pass
        print(f"  [{i + 1}s] waiting...")

    if not data:
        print("No packet captured. Try again — press the button once quickly after starting.")
        sys.exit(1)

    timings = _decode_b1_timings(data)
    fan_id = _extract_fan_id(timings)

    if not fan_id:
        print("Captured a packet but could not decode the fan ID. Try again.")
        sys.exit(1)

    print(f"\n{'=' * 40}")
    print(f"  Fan ID captured: {fan_id}")
    print(f"{'=' * 40}")
    print(f"\nUse this ID when adding the device in Home Assistant.")
    print(f"To contribute it to the community, open a PR and add it to")
    print(f"custom_components/shark_flex_breeze/known_ids.json\n")


if __name__ == "__main__":
    main()
