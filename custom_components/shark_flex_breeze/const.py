DOMAIN = "shark_flex_breeze"

CONF_TRANSMITTER = "transmitter"
CONF_FAN_ID = "fan_id"
CONF_FAN_NAME = "fan_name"

# RF timing (microseconds) — verified from learned remote capture
FREQ_HZ = 433_920_000
SYNC_US = 4400       # sync burst
LONG_US = 920        # long pulse  = bit 0
SHORT_US = 296       # short pulse = bit 1
GAP_US = 296         # short gap (follows LONG pulse / bit 0)
LONG_GAP_US = 920    # long gap  (follows SHORT pulse / bit 1)
RESET_US = 9300      # inter-repetition gap (also follows SYNC)
PACKET_BITS = 41
REPEAT_COUNT = 5     # repetitions of bit sequence after single SYNC burst

COMMAND_SUFFIXES: dict[str, str] = {
    "power":          "aa558",
    "speed_increase": "d8278",
    "speed_decrease": "b54a8",
    "turbo":          "ec138",
    "swing_increase": "a6598",
    "swing_decrease": "97688",
    "rotate_left":    "e31c8",
    "rotate_right":   "cb348",
}

PRESET_NORMAL = "Normal"
PRESET_TURBO = "Turbo"
PRESET_MODES = [PRESET_NORMAL, PRESET_TURBO]
