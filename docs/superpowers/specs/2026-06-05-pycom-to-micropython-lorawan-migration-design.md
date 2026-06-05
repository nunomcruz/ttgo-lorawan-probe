# Migration: Pycom MicroPython → custom MicroPython (LoRaWAN) — Design

**Date:** 2026-06-05
**Status:** Approved (pending implementation plan)

## Goal

Port the TTGO T-Beam LoRaWAN range-survey probe from Pycom MicroPython to the
custom MicroPython firmware at `~/Work/esp/micropython-lorawan/`, which provides
a native `lorawan` USER_C_MODULE and a `tbeam` board-support module. Behaviour
(GPS-driven datarate sweep, TTN-Mapper payload, OLED layout, downlink-driven
distance/gateway display, hardware shutdown) must be preserved.

## Key decisions

1. **Activation: ABP**, keyed per-device by `binascii.hexlify(machine.unique_id())`
   (replacing the Pycom-only `lora.mac()` key). Matches the existing TTN device
   provisioning; no over-the-air join in the field. FCntUp persisted via NVS.
2. **PMU: full driver port.** Keep the vendored `axp202.py`, `AXP2101.py`,
   `I2CInterface.py`, `constants.py`. They already implement `shutdown()` and the
   charge-LED modes the probe uses. No minimal re-implementation.
3. **Config: keep per-device overrides** (pins, display, rotate) that default to
   `tbeam.detect()` when absent. Pin values become GPIO integers, not Pycom
   `'Gxx'` strings.

## API mapping (Pycom → target)

| Concern | Pycom (current) | Target firmware |
|---|---|---|
| Radio + MAC | `network.LoRa` + `socket.AF_LORA` | `lorawan.LoRaWAN(region=lorawan.EU868, rx2_datarate=lorawan.DR_3)` |
| Join (ABP) | `lora.join(LoRa.ABP, auth=(dev_addr, nwk, app))` | `lw.join_abp(dev_addr=, nwk_s_key=, app_s_key=)` |
| Custom channels | `lora.add_channel(index, frequency, dr_min, dr_max)` | `lw.add_channel(index, frequency, dr_min, dr_max)` (same signature) |
| DR per uplink | `sock.setsockopt(SOL_LORA, SO_DR, dr)` | `lw.send(payload, datarate=dr)` per send |
| Uplink | `sock.send(bytes(payload))` | `lw.send(payload, port=1, datarate=dr)` |
| Downlink | `sock.recv(64)` after `sleep(2)` | `lw.recv(timeout=2)` → `(data, port, rssi, snr, multicast)` or `None` |
| FCnt persist | `lora.nvram_restore()` | `lw.nvram_restore()` / `lw.nvram_save()` |
| Device id (config key) | `lora.mac()` | `machine.unique_id()` |
| GPS UART | `UART(1, 9600, pins=uart_pins)` | `tbeam.gps_uart(hw)` (rx=34/tx=12; v0.7 rx=12/tx=15) |
| Display I2C | `I2C(1, pins=...)` | `tbeam.i2c_bus()` (I2C(0), scl=22/sda=21) |
| PMU I2C | `I2C(0, pins=('G21','G22'))` | `tbeam.i2c_bus()` passed into the PMU driver |
| Status LED | `Pin('G14', Pin.OUT)` | `Pin(<gpio int>, Pin.OUT)` (default `tbeam.LED` = 4) |
| Shutdown IRQ | `pin.callback(Pin.IRQ_FALLING, fn)` | `pin.irq(trigger=Pin.IRQ_FALLING, handler=fn)` |
| WiFi off | `WLAN().deinit()` | `network.WLAN(network.STA_IF).active(False)` |

- `DR_0..DR_5` map 1:1 to the existing `TEST_DATARATES` integers (0=SF12 … 5=SF7);
  config values carry over unchanged.
- ADR stays **off** (`lw.adr(False)`) — the probe's purpose is a manual DR sweep.

## File-by-file plan

### Rewritten
- **`main.py`** — replace radio/socket/PMU init.
  - Boot: `hw = tbeam.detect()`; construct `i2c = tbeam.i2c_bus()` once.
  - PMU init dispatches on `hw.pmu`: `"axp192"` → `axp202.PMU(i2c=i2c, address=axp202.AXP192_SLAVE_ADDRESS)` + the existing LDO2/LDO3/ADC/charge-LED setup; `"axp2101"` → `AXP2101(i2c)` + the existing ALDO2/ALDO3/TS-pin/measure/LED setup; `None` → no PMU (v0.7).
  - LoRaWAN: `lw = lorawan.LoRaWAN(region=lorawan.EU868, rx2_datarate=lorawan.DR_3)`; `lw.nvram_restore()`; on `OSError` provision ABP via `lw.join_abp(...)`; keep `lw.add_channel(...)` for channels 3–7 (867.1–867.9 MHz); `lw.adr(False)`.
  - Config key: `binascii.hexlify(machine.unique_id()).upper().decode()`. Print it at boot so each board can be added to `config.py` (same one-time step as the old LoRa MAC).
  - Main loop: unchanged structure. Uplink → `lw.send(bytes(gps_array), port=1, datarate=dr)`; downlink → `pkt = lw.recv(timeout=2)`; if `pkt`, unpack `data, port, rssi, snr, multicast` and apply `data[0]`=distance, `data[1:]`=gateway name.
  - LED branches (`None` / `"AXP"` / pin) preserved; AXP path keeps `setChgLEDMode` / `setChargingLedMode`.
  - Shutdown handler unchanged except button wiring: `pin.irq(trigger=Pin.IRQ_FALLING, handler=shutdown)`.

### Ported (minimal change)
- **`lib/axp202.py`** — only Pycom-specific line is the internal I2C build (`I2C(0, pins=...)`). Change `PMU.__init__` to accept an `i2c` bus (like `AXP2101` already does); when supplied, skip internal bus construction. Default pins become GPIO ints (sda=21, scl=22, intr=35) as fallback. Register I/O already uses stock `writeto_mem` / `readfrom_mem_into`.
- **`lib/gps_data.py`** — UART from `tbeam.gps_uart(hw)` (or per-device pin override). MicropyGPS logic and the TTGO V1.1 UBX baud-rate workaround unchanged.
- **`lib/data_display.py`** — logic unchanged (uses `_thread`, available on ESP32). I2C now comes from `tbeam.i2c_bus()`.
- **`lib/config.py`** — keyed by `unique_id()` hex. Per-device: ABP keys (`DEV_ADDR`, `APPS_KEY`, `NWS_KEY`), `TEST_DATARATES`, `TEST_MSG_SENDS`, `ROTATE_DISPLAY`, and **optional** pin overrides (`GPS_UART_PINS`, `I2C_PINS`, `LED_PIN`, `SHUTDOWN_PIN`, `POWER_DISPLAY`) defaulting to `tbeam.detect()` when absent. Pin values as GPIO ints.
- **`boot.py`** — reduced to disabling WiFi/BT for power; drop all Pycom telnet/AP/`known_nets` code.

### Unchanged
- **`lib/lopylcd.py`** — already stock-I2C (`writeto`, `readfrom_mem`).
- **`lib/AXP2101.py`**, **`lib/I2CInterface.py`**, **`lib/constants.py`** — already standard MicroPython.
- **`lib/micropygps.py`** — portable NMEA parser.

### Deleted
- Nothing in `lib/`. Only the Pycom `network`/`socket` usage in `main.py` and the WiFi code in `boot.py` are removed.

## Data flow (unchanged semantics)

GPS NMEA → MicropyGPS → `GPS_data.convert_payload` → 10-byte TTN-Mapper frame
(lat/lon 3 B each, alt 2 B, HDOP 1 B, sat count 1 B) → `lw.send(..., datarate=dr)`
→ `lw.recv(timeout=2)` → `data[0]`=distance (km), `data[1:]`=gateway name (UTF-8)
→ OLED via `set_distance` / `set_gateway`.

## Error handling

- `lw.send` raises `OSError` / `RuntimeError` (not socket errors). Handle
  `OSError(EBUSY)` (duty cycle) by sleeping `lw.time_until_tx()` ms then retrying;
  other send errors → flash message + `machine.reset()` (preserving today's
  reset-on-error behaviour, improved by the duty-cycle backoff).
- PMU init guarded so a board with no PMU (v0.7) degrades gracefully, as today.
- Missing ABP keys for the current `unique_id` → clear error at boot.

## Testing / verification

No host-runnable code and no on-device test harness exist. Verification is
manual on-device:
1. Boot → serial prints the `unique_id` config key and `tbeam.detect()` result.
2. GPS acquires a fix (OLED shows "Got GPS Fix!").
3. Uplinks appear on TTN at DR0/DR3/DR5; payload decodes via the README formatter.
4. Position plotted on TTN Mapper.
5. Shutdown button powers the board off via the PMU.

A short "verifying the migration" checklist will be added to `README.md`; no
automated test suite is introduced.

## Out of scope

- OTAA support (ABP retained).
- ADR-driven operation (manual DR sweep retained).
- Class B/C, multicast, time sync (firmware supports them; the probe does not need them).
