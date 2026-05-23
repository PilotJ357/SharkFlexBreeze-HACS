DOMAIN = "shark_flex_breeze"

CONF_TRANSMITTER = "transmitter"
CONF_FAN_ID = "fan_id"
CONF_FAN_NAME = "fan_name"

# RF timing (microseconds)
FREQ_HZ = 433_920_000
SYNC_US = 4224
LONG_US = 888    # bit 1
SHORT_US = 308   # bit 0
GAP_US = 292     # inter-symbol gap
RESET_US = 9000  # inter-packet gap
PACKET_BITS = 41
REPEAT_COUNT = 1

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
