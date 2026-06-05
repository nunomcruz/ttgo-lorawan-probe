# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A LoRaWAN range-survey probe for the TTGO T-Beam running a custom **MicroPython firmware** with a native `lorawan` module (fork at `~/Work/esp/micropython-lorawan/`). It reads GPS, then transmits the position at several spreading factors (datarates) so coverage can be mapped on TTN Mapper. There is no build system, package manager, or test suite — this is firmware that runs on-device.

## Runtime & deployment

- Target: custom MicroPython build (fork at `~/Work/esp/micropython-lorawan/`), not stock MicroPython or CPython. LoRaWAN is handled by `import lorawan` (`lorawan.LoRaWAN`); hardware discovery by `import tbeam` (`tbeam.detect()` for radio/PMU/GPS-pin/OLED detection, `tbeam.i2c_bus()` for the shared I2C bus). Pins are GPIO integers, not Pycom `'Gxx'` names. Do not assume CPython stdlib behaviour.
- Deploy by copying files to the device flash (e.g. with `rshell` or `ampy`). `lib/` must land in the device's `lib/` directory (it's on the MicroPython import path).
- Boot order: the firmware runs `boot.py` first (disables WiFi/BT for power), then `main.py` (the application).
- There is no way to run this code off-device. Don't try to execute `main.py` or the `lib/` modules with a host Python interpreter.

## Configuration

All per-device settings live in `lib/config.py` and are **keyed by the board's unique hardware id** (`DEVICE_CONFIG[device_id]`), where the key is `binascii.hexlify(machine.unique_id()).upper().decode()` — printed at boot as `Device id: <hex>`. Each physical board needs its own entry. Per-device keys: ABP credentials (`DEV_ADDR`, `APPS_KEY`, `NWS_KEY`), and optional GPIO integer overrides for `GPS_UART_PINS`, `I2C_PINS`, `LED_PIN`, `ROTATE_DISPLAY`, `SHUTDOWN_PIN`, and `POWER_DISPLAY`. When a pin override is absent, `tbeam.detect()` supplies the default.

**Never commit real credentials.** The checked-in `config.py` contains placeholders (`"yourkeyhere"`). Keep them as placeholders in any committed change.

## Architecture

`main.py` is the whole application: a single top-level loop (not wrapped in `main()`), no functions except the `shutdown` IRQ handler. Flow:

1. **Power management** — call `tbeam.detect()` to get a `HardwareInfo` (`hw`). The `.pmu` field (`'axp192'`, `'axp2101'`, or `None`) selects the driver: AXP192 via `axp202.PMU(i2c=..., address=...)`, AXP2101 via `AXP2101.py`. PMU controls power rails for the LoRa radio and GPS, plus the charge LED (which doubles as the status LED when `LED_PIN == "AXP"`). On AXP2101, `disableTSPinMeasure()` is called because these boards have no battery thermistor — leaving it enabled gives bad readings or cuts power.
2. **LoRa join** — `lorawan.LoRaWAN(region=lorawan.EU868, rx2_datarate=lorawan.DR_3)`, joins via **ABP** with `lw.join_abp(dev_addr=int, nwk_s_key=bytes, app_s_key=bytes)`. ADR is disabled (manual datarate sweep). Frame counter restored from NVRAM via `lw.nvram_restore()` / saved via `lw.nvram_save()`. Uplinks: `lw.send(payload, port=1, datarate=dr)`. Downlinks: `lw.recv(timeout=2)` returns `(data, port, rssi, snr, multicast)` or `None`.
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
- `lib/AXP2101.py`, `lib/I2CInterface.py` — X-Power PMU drivers (lewisxhe)
- `lib/constants.py` — AXP202/AXP192 register & constant definitions
- `lib/lopylcd.py` — OLED display driver

`lib/axp202.py` originated as a lewisxhe upstream driver but has been locally modified to accept an injected I2C bus (`axp202.PMU(i2c=..., address=...)`) and integer default pins. It is no longer pristine upstream — treat it as locally-maintained.

The locally-authored code is `main.py`, `boot.py`, `lib/config.py`, `lib/gps_data.py`, `lib/data_display.py`, and the now-modified `lib/axp202.py`.

## Conventions specific to this codebase

- `config.DEBUG` gates verbose serial logging; respect it when adding diagnostics.
- The `LED_PIN` value is overloaded: a GPIO integer (e.g. `14`), the string `"AXP"` (use the PMU charge LED), or `None`. LED handling is centralised in the module-level `set_led(on)` helper in `main.py`, which covers all three forms (and the AXP192/AXP2101 split for the charge-LED path); call sites just call `set_led(...)`.
- Memory matters on-device: `gc` calls are present but commented out. Be conscious of allocations in the loop.
