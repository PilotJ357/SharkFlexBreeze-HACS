# Shark Flex Breeze

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/PilotJ357/SharkFlexBreeze-HACS?style=flat-square)](https://github.com/PilotJ357/SharkFlexBreeze-HACS/releases)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2026.5%2B-blue?style=flat-square)](https://www.home-assistant.io/)
[![License](https://img.shields.io/github/license/PilotJ357/SharkFlexBreeze-HACS?style=flat-square)](LICENSE)

_Control SharkFlexBreeze tower fans from Home Assistant via native RF capabilities._

---

<!-- TOC -->
* [AI Disclosure](#ai-disclosure)
* [Installation](#installation)
* [Setup](#setup)
* [Features](#features)
* [Hardware](#hardware)
* [Finding Your Fan ID](#finding-your-fan-id)
* [Contributing](#contributing)
* [RF Protocol](#rf-protocol)
* [Notes](#notes)
<!-- TOC -->

---

## AI Disclosure

This entire integration was build with Claude Code because I wanted to control these fans through HA's new RF support. I make no claims to be an expert developer but I've tried my best to (have Claude) follow best practices. I welcome improvements if there are issues. I promise, if I had attempted to hodge-podge this together, I'd never share it because it would probaly "work" well enough for my own use in the worst ways. Let's be honest, despite having a ham license, SDRs are an enigma to me. Claude reverse engineered the RF commands in <30 minutes. 

---

## Installation

**Method 1.** HACS → Integrations → ⋮ → Custom repositories → add this repo as **Integration** → search "Shark Flex Breeze" → Download → Restart HA

**Method 2.** Copy `custom_components/shark_flex_breeze/` into your HA `config/custom_components/` → Restart HA

---

## Setup

> **Make sure the fan is physically off before starting setup.** The test step sends a power toggle — if the fan is already on, it will turn off instead of on, and HA's initial state will be wrong.

1. **Settings → Devices & Services → Add Integration → "Shark Flex Breeze"**
2. Select your RF transmitter entity
3. Enter a name for the fan (e.g. *Bedroom Fan*)
4. Choose a previously captured fan ID from the dropdown, or enter a new one
   - No ID yet? Run [`scripts/get_fan_id.sh`](#finding-your-fan-id) first
5. A test power command is sent — confirm the fan toggled on
6. Done — a `fan.*` entity appears under the device

Repeat for each fan.

---

## Features

- **5-speed control** — 20 / 40 / 60 / 80 / 100 %
- **Turbo preset** — dedicated turbo mode; automatically exits when a speed is selected
- **Oscillation** — swing increase / decrease
- **Rotate buttons** — rotate left / rotate right as momentary button presses
- **State restore** — survives HA restarts (assumed state)
- **Multi-fan** — add as many fans as you have remotes; each gets its own device

---

## Hardware

This integration requires a compatible RF transmitter added to Home Assistant. See the [Radio Frequency integration docs](https://www.home-assistant.io/integrations/radio_frequency) for supported hardware and setup instructions.

---

## Finding Your Fan ID

Each remote has a unique 24-bit RF ID hardwired at the factory. **It does not appear to be derived from the serial number** — I don't yet know how IDs are assigned or whether there are patterns across units.

The config flow includes a dropdown of **community-contributed IDs** (see [`known_ids.json`](custom_components/shark_flex_breeze/known_ids.json)). If you don't have an SDR, try those first — your fan may share an ID with a known remote. If none work, you'll need to capture yours.

> **No SDR?** Try the community IDs. If one works, great. If not, you'll need to capture yours with an RTL-SDR dongle.

### Option A: Capture with Broadlink RM4 Pro (recommended)

If you already have a Broadlink device in HA, this is the easiest path — no extra hardware required.

**Requirements:** Python 3 + `broadlink` library
```bash
pip3 install broadlink
```

**Capture:**
```bash
python3 scripts/get_fan_id_broadlink.py 192.168.1.x
```

Replace `192.168.1.x` with your Broadlink device's IP address. Follow the on-screen prompts — hold a button to lock the frequency, then press once to capture.

Output:
```
Fan ID captured: 0e37ee

Use this ID when adding the device in Home Assistant.
```

---

### Option B: Capture with RTL-SDR

**Requirements:** RTL-SDR dongle + `rtl_433`
```bash
brew install rtl_433      # macOS
sudo apt install rtl-433  # Linux
```

**Capture:**
```bash
./scripts/get_fan_id.sh bedroom
```

Point your remote at the dongle and press any button. Output:
```
Fan ID captured: 0e37ee

Use this ID when adding the device in Home Assistant.
```

---

## Contributing

Fan IDs are the main thing to figure out. I don't know how many unique IDs exist, whether there are patterns, or how they're assigned.

**If you find a new ID — or figure out how they're encoded — please [open a PR](https://github.com/PilotJ357/SharkFlexBreeze-HACS/pulls)** to add it to [`known_ids.json`](custom_components/shark_flex_breeze/known_ids.json). The more IDs we collect, the more useful the "try a community ID" flow becomes for people without an SDR.

---

## RF Protocol

Reverse-engineered via RTL-SDR (RTL2838) + rtl_433.

| Parameter | Value |
|-----------|-------|
| Frequency | 433.87 MHz (measured) |
| Modulation | OOK PWM (ASK) |
| Packet length | 41 bits |
| Repeats per burst | 5× (one sync, five bit-sequence repetitions) |
| Sync pulse | ~4400 µs |
| Bit 0 (long pulse) | ~920 µs + ~296 µs gap |
| Bit 1 (short pulse) | ~296 µs + ~920 µs gap |
| Post-sync / inter-rep gap | ~9300 µs |

**Packet structure:** `[ bits 0–23 : Fan ID ][ bits 24–40 : Command ]`

**rtl_433 flex decoder:**
```
n=fan_remote,m=OOK_PWM,s=296,l=920,r=9300,t=150,y=4400
```

<details>
<summary>Full command map</summary>

Codes are built by concatenating the 24-bit fan ID prefix with the 17-bit command suffix.

| Command | Suffix | Fan 1 (`0e37ee`) | Fan 2 (`0797ef`) |
|---------|--------|------------------|------------------|
| Power (toggle) | `aa558` | `0e37eeaa558` | `0797efaa558` |
| Speed increase | `d8278` | `0e37eed8278` | `0797efd8278` |
| Speed decrease | `b54a8` | `0e37eeb54a8` | `0797efb54a8` |
| Turbo | `ec138` | `0e37eeec138` | `0797efec138` |
| Swing increase | `a6598` | `0e37eea6598` | `0797efa6598` |
| Swing decrease | `97688` | `0e37ee97688` | `0797ef97688` |
| Rotate left | `e31c8` | `0e37eee31c8` | `0797efe31c8` |
| Rotate right | `cb348` | `0e37eecb348` | `0797efcb348` |

</details>

---

## Notes

- **State tracking is best-effort** — the fan gives no feedback over RF. If the fan is operated via its physical remote, HA's assumed state will drift and get out of sync.
- **Power is a toggle** — one code for both on and off. If HA's state is wrong, a `turn_on` call may actually turn it off.
- **Turbo/burst is also a toggle** — same situation: one code enters and exits burst mode. Pressing turbo while in turbo returns the fan to its previous speed automatically. Setting a speed percentage while in turbo will automatically send the exit-turbo command first, then adjust speed.
- **5 speed levels, not 4** — speed increase/decrease are relative ±1 commands; the remote has no "go to level N" command. The integration tracks assumed current level and sends the required number of presses to reach the target. If state has drifted, the delta will be wrong.
- **Not rolling code** — static codes, replay reliably.
- **Fan ID is not serial-derived** — hardwired in the remote at the factory; must be captured via RTL-SDR.

---

<details>
<summary>Project structure</summary>

```
SharkFlexBreezeHACS/
├── hacs.json
├── README.md
├── icon.png
├── scripts/
│   ├── get_fan_id.sh               # capture fan ID via RTL-SDR
│   └── get_fan_id_broadlink.py     # capture fan ID via Broadlink RM4 Pro
└── custom_components/shark_flex_breeze/
    ├── __init__.py
    ├── button.py
    ├── config_flow.py
    ├── const.py
    ├── entity.py
    ├── fan.py
    ├── known_ids.json
    ├── manifest.json
    ├── strings.json
    └── translations/
        └── en.json
```

</details>
