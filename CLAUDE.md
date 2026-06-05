# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A LoRaWAN range-survey probe for the TTGO T-Beam running **Pycom MicroPython firmware**. It reads GPS, then transmits the position at several spreading factors (datarates) so coverage can be mapped on TTN Mapper. There is no build system, package manager, or test suite — this is firmware that runs on-device.

## Runtime & deployment

- Target: Pycom MicroPython (not standard MicroPython or CPython). APIs like `network.LoRa`, `network.WLAN`, `machine`, `socket.AF_LORA`, and Pycom pin names (`'G15'`, `'G21'`, …) only exist on this firmware. Do not assume CPython stdlib behaviour.
- Deploy by copying files to the device flash (e.g. with `pymakr`, `rshell`, or `ampy`). `lib/` must land in the device's `lib/` directory (it's on the MicroPython import path).
- Boot order: the firmware runs `boot.py` first (serial + WiFi setup), then `main.py` (the application).
- There is no way to run this code off-device. Don't try to execute `main.py` or the `lib/` modules with a host Python interpreter.

## Configuration

All per-device settings live in `lib/config.py` and are **keyed by the board's LoRa MAC address** (`DEVICE_CONFIG[lora_mac]`). The MAC is read at runtime via `lora.mac()` in `main.py`, so each physical board needs its own entry. Per-device keys: ABP credentials (`DEV_ADDR`, `APPS_KEY`, `NWS_KEY`), `GPS_UART_PINS`, `I2C_PINS` (display), `TEST_DATARATES`, `TEST_MSG_SENDS`, `LED_PIN`, `ROTATE_DISPLAY`, `SHUTDOWN_PIN`, and the optional `POWER_DISPLAY` (IO pin to power displays with GND/VCC swapped — read inside a `try/except`, so it may be omitted).

`boot.py` holds WiFi SSIDs/passwords in the `known_nets` dict.

**Never commit real credentials.** The checked-in `config.py` and `boot.py` contain placeholders (`"yourkeyhere"`, `KNOWN_SSID_NETWORK`/`PASSWORD`, `RANDOMPASSWORD`). Keep them as placeholders in any committed change.

## Architecture

`main.py` is the whole application: a single top-level loop (not wrapped in `main()`), no functions except the `shutdown` IRQ handler. Flow:

1. **Power management** — initialise the PMU. The board has two hardware variants detected at runtime: AXP192 (older, via `axp202.py`) and AXP2101 (T-Beam 1.2, via `AXP2101.py`). `main.py` tries AXP192 first and falls back to AXP2101 in an `except`. PMU controls power rails for the LoRa radio and GPS, plus the charge LED (which doubles as the status LED when `LED_PIN == "AXP"`). On AXP2101, `disableTSPinMeasure()` is called because these boards have no battery thermistor — leaving it enabled gives bad readings or cuts power.
2. **LoRa join** — `LoRa(mode=LORAWAN, region=EU868)`, adds EU868 channels, joins via **ABP** (OTAA code is present but commented). Restores frame counter from NVRAM.
3. **GPS** — `gps_data.GPS_data` (wraps the vendored `micropygps.py`). Includes a workaround for the TTGO V1.1 GPS that fails to emit data until sent a UBX baud-rate command (see `gps_data.py`).
4. **Main loop** — wait for a GPS fix, then for each datarate in `TEST_DATARATES` send `TEST_MSG_SENDS` uplinks on port 1.

### LoRa payload

`GPS_data.convert_payload` builds the **TTN Mapper byte format**: lat/lon each packed into 3 bytes scaled over the full range, 2-byte altitude, 1-byte HDOP (×10), 1-byte satellite count — 10 bytes total. The TTN payload-formatter decoder that matches this is in `README.md`.

### Downlink handling

After each uplink `main.py` reads a downlink: `data[0]` is interpreted as distance (km) and `data[1:]` as the gateway name (UTF-8). These are shown on the display via `set_distance` / `set_gateway`.

### Display

`lib/data_display.py` (`DATA_display`) renders a fixed 8-line OLED layout over `lib/lopylcd.py` (a 128×64 SSD1306-style driver). It holds display state as class attributes and re-renders on every `set_*` setter call. `flash_message()` shows a transient message that reverts after a couple of refreshes.

## Vendored libraries — do not edit unless necessary

These are third-party drivers; treat as upstream:
- `lib/micropygps.py` — NMEA parser (MicropyGPS)
- `lib/axp202.py`, `lib/AXP2101.py`, `lib/I2CInterface.py` — X-Power PMU drivers (lewisxhe)
- `lib/constants.py` — AXP202/AXP192 register & constant definitions
- `lib/lopylcd.py` — OLED display driver

The locally-authored code is `main.py`, `boot.py`, `lib/config.py`, `lib/gps_data.py`, and `lib/data_display.py`.

## Conventions specific to this codebase

- `config.DEBUG` gates verbose serial logging; respect it when adding diagnostics.
- The `LED_PIN` value is overloaded: a pin name (e.g. `'G14'`), the string `"AXP"` (use the PMU charge LED), or `None`. LED handling is duplicated across several call sites in `main.py` — keep the three branches consistent if you touch one.
- Memory matters on-device: `gc` calls are present but commented out. Be conscious of allocations in the loop.
