# Pycom → MicroPython LoRaWAN Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the TTGO T-Beam LoRaWAN range-survey probe from Pycom MicroPython to the custom MicroPython firmware (native `lorawan` + `tbeam` modules), preserving all behaviour.

**Architecture:** Single-loop application unchanged in shape. Radio/MAC swaps from `network.LoRa`+`socket.AF_LORA` to `lorawan.LoRaWAN`; hardware pins come from `tbeam.detect()`; the vendored AXP PMU drivers are kept (only `axp202.py` needs a one-line I2C-bus injection). ABP activation retained, keyed by `machine.unique_id()`.

**Tech Stack:** MicroPython (custom fork at `~/Work/esp/micropython-lorawan/`), `lorawan` USER_C_MODULE, `tbeam` board module, MicropyGPS, SSD1306 OLED.

**Spec:** `docs/superpowers/specs/2026-06-05-pycom-to-micropython-lorawan-migration-design.md`

**Verification note:** This is on-device firmware; it cannot run on a host and has no automated test suite. The per-task automated gate is `python3 -m py_compile <file>` (checks syntax — MicroPython-only imports are *not* resolved at compile time, so this passes despite `import machine`/`lorawan`). Behaviour is verified manually on-device in the final task. `SyntaxWarning` lines from py_compile are acceptable; a non-zero exit (a real `SyntaxError`) is not.

---

### Task 1: Port `lib/axp202.py` to standard-MicroPython I2C

The only Pycom-specific code in the AXP192 driver is the internal I2C construction (`I2C(0, pins=...)`) and the `'Gxx'` default pin names. Make `PMU.__init__` accept an injected `i2c` bus (matching `AXP2101`), and convert default pins to GPIO integers. Register I/O already uses stock `writeto_mem`/`readfrom_mem_into` and is untouched.

**Files:**
- Modify: `lib/axp202.py:37-39` (default pins), `lib/axp202.py:44-64` (`__init__` + `init_i2c`)

- [ ] **Step 1: Convert default pin names to GPIO integers**

Replace lines 37-39:

```python
default_pin_scl = 22
default_pin_sda = 21
default_pin_intr = 35
```

- [ ] **Step 2: Accept an injected I2C bus in `__init__`**

Replace the `__init__` body (lines 44-60) so a supplied bus skips internal pin/bus construction:

```python
    def __init__(self, scl=None, sda=None,
                 intr=None, address=None, i2c=None):
        self.device = None
        self.scl = scl if scl is not None else default_pin_scl
        self.sda = sda if sda is not None else default_pin_sda
        self.intr = intr if intr is not None else default_pin_intr
        self.chip = default_chip_type
        self.address = address if address else AXP202_SLAVE_ADDRESS

        self.buffer = bytearray(16)
        self.bytebuf = memoryview(self.buffer[0:1])
        self.wordbuf = memoryview(self.buffer[0:2])
        self.irqbuf = memoryview(self.buffer[0:5])

        if i2c is not None:
            self.bus = i2c
        else:
            self.init_pins()
            self.init_i2c()
        self.init_device()
```

- [ ] **Step 3: Make `init_i2c` use standard-MicroPython I2C**

Replace `init_i2c` (lines 62-64):

```python
    def init_i2c(self):
        print('* initializing i2c')
        self.bus = I2C(0, scl=self.pin_scl, sda=self.pin_sda)
```

- [ ] **Step 4: Syntax gate**

Run: `python3 -m py_compile lib/axp202.py`
Expected: exit 0 (no `SyntaxError`).

- [ ] **Step 5: Commit**

```bash
git add lib/axp202.py
git commit -m "Port axp202 PMU driver to standard MicroPython I2C"
```

---

### Task 2: Rewrite `boot.py` to disable WiFi/BT only

The Pycom `boot.py` does serial-over-UART duplication and WiFi STA/AP setup with `known_nets` — all Pycom-specific. Replace with a minimal power-saving boot that disables WiFi and Bluetooth.

**Files:**
- Modify: `boot.py` (full replacement)

- [ ] **Step 1: Replace `boot.py` entirely**

```python
# boot.py — runs before main.py.
# The probe is LoRa-only; disable WiFi and Bluetooth to save power.

import network

try:
    network.WLAN(network.STA_IF).active(False)
    network.WLAN(network.AP_IF).active(False)
except Exception as err:
    print("WiFi disable skipped:", err)

try:
    import bluetooth
    bluetooth.BLE().active(False)
except Exception as err:
    print("BT disable skipped:", err)
```

- [ ] **Step 2: Syntax gate**

Run: `python3 -m py_compile boot.py`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add boot.py
git commit -m "Replace Pycom WiFi boot with minimal radio-off boot"
```

---

### Task 3: Restructure `lib/config.py` (keyed by `unique_id`, GPIO ints)

Drop the Pycom `'Gxx'` pin defaults. Key per-device config by `binascii.hexlify(machine.unique_id()).upper().decode()`. Keep optional pin overrides as GPIO integers; omitting them falls through to `tbeam.detect()` in `main.py`.

**Files:**
- Modify: `lib/config.py` (full replacement)

- [ ] **Step 1: Replace `lib/config.py` entirely**

```python
# Per-device configuration for the LoRaWAN probe.
#
# DEVICE_CONFIG is keyed by the board's unique id:
#   binascii.hexlify(machine.unique_id()).upper().decode()
# main.py prints this key at boot — copy it into a new entry below.
#
# Pin overrides are OPTIONAL and use GPIO integers (not 'Gxx' strings).
# Omit any of them to use the value from tbeam.detect().
#   GPS_UART_PINS = (rx, tx)   I2C_PINS = (scl, sda)
#   LED_PIN = <gpio int> | "AXP" | None
#   SHUTDOWN_PIN = <gpio int>  POWER_DISPLAY = <gpio int>

GPS_READ_INTERVAL = 0.3   # seconds between GPS reads when off-network
TIME_BETWEEN_UPLINKS = 0  # seconds between uplinks in the DR sweep

DEBUG = True

DEVICE_CONFIG = {
    "UNIQUEID": {  # replace with the id printed at boot
        # ABP credentials (from your LNS / TTN console)
        "DEV_ADDR": "yourdevaddrhere",  # hex string, no 0x, e.g. "260B1234"
        "APPS_KEY": "yourkeyhere",      # 32 hex chars
        "NWS_KEY": "yourkeyhere",       # 32 hex chars
        # Datarates to sweep: 0=SF12 1=SF11 2=SF10 3=SF9 4=SF8 5=SF7
        "TEST_DATARATES": (0, 3, 5),
        "TEST_MSG_SENDS": 1,            # uplinks per datarate
        "ROTATE_DISPLAY": True,
        # --- optional pin overrides (GPIO ints); omit to use tbeam.detect() ---
        # "GPS_UART_PINS": (34, 12),
        # "I2C_PINS": (22, 21),
        # "LED_PIN": 4,
        # "SHUTDOWN_PIN": 38,
        # "POWER_DISPLAY": 2,
    },
}
```

- [ ] **Step 2: Syntax gate**

Run: `python3 -m py_compile lib/config.py`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add lib/config.py
git commit -m "Key device config by unique_id; GPIO-int pin overrides"
```

---

### Task 4: Port `lib/gps_data.py` to standard-MicroPython UART

Change the UART construction from Pycom `UART(1, 9600, pins=...)` to standard `UART(1, baudrate=9600, rx=, tx=)`, taking explicit `rx`/`tx` GPIO integers. The MicropyGPS parsing, the TTGO V1.1 UBX baud-rate workaround, and `convert_payload` are unchanged.

**Files:**
- Modify: `lib/gps_data.py:14-16` (`__init__` signature + UART line)

- [ ] **Step 1: Update `__init__` to take `rx`/`tx` and build a standard UART**

Replace lines 14-16:

```python
    def __init__(self, rx, tx):
        self.uart = UART(1, baudrate=9600, rx=rx, tx=tx)
        time.sleep(0.5)
```

(Everything below — the MicropyGPS init, the `if not self.uart.any():` UBX workaround, `convert_payload`, `get_loc`, `has_fix` — stays exactly as is.)

- [ ] **Step 2: Syntax gate**

Run: `python3 -m py_compile lib/gps_data.py`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add lib/gps_data.py
git commit -m "Port GPS UART to standard MicroPython rx/tx pins"
```

---

### Task 5: Rewrite `main.py` for `lorawan` + `tbeam`

Full replacement. Hardware via `tbeam.detect()`; one shared `tbeam.i2c_bus()` for PMU and OLED; PMU dispatched on `hw.pmu` (verbatim rail/LED/ADC setup from the Pycom build); ABP join via `lw.join_abp`; DR sweep via `lw.send(..., datarate=dr)`; downlink via `lw.recv(timeout=2)`; a module-level `set_led()` helper replaces the five duplicated LED branches (and uses `==`/`!=`, fixing the old `is "AXP"` identity-comparison bug); shutdown button via `pin.irq(...)`.

**Files:**
- Modify: `main.py` (full replacement)

- [ ] **Step 1: Replace `main.py` entirely**

```python
"""
LoRaWAN Probe — sends multiple uplinks at different datarates to survey range,
embedding GPS position (TTN Mapper byte format) and a per-run counter.
TTGO T-Beam on custom MicroPython firmware (native lorawan + tbeam modules).

@author Nuno Cruz aka nunomcruz
"""

import time
import errno
import binascii
import machine
from machine import Pin

import config
import lorawan
import tbeam

import axp202
from AXP2101 import AXP2101

import gps_data
from data_display import DATA_display


# --- Hardware detection (radio, PMU, GPS pins, OLED presence) ---
hw = tbeam.detect()
print("tbeam:", hw)

i2c = tbeam.i2c_bus()   # shared bus: PMU @0x34, OLED @0x3C

# --- PMU init. Rails default on at reset; we set voltages + charge LED like
#     the Pycom build did. Dispatch on the detected chip. ---
axp = None
if hw.pmu == "axp192":
    axp = axp202.PMU(i2c=i2c, address=axp202.AXP192_SLAVE_ADDRESS)
    axp.setLDO2Voltage(3300)   # LoRa VDD 3v3
    axp.setLDO3Voltage(3300)   # GPS VDD 3v3
    axp.enablePower(axp202.AXP192_LDO3)
    axp.enablePower(axp202.AXP192_LDO2)
    axp.enableADC(axp202.AXP202_ADC1, axp202.AXP202_VBUS_VOL_ADC1)
    axp.enableADC(axp202.AXP202_ADC1, axp202.AXP202_VBUS_CUR_ADC1)
    axp.enableADC(axp202.AXP202_ADC1, axp202.AXP202_BATT_VOL_ADC1)
    axp.enableADC(axp202.AXP202_ADC1, axp202.AXP202_BATT_CUR_ADC1)
    axp.setChgLEDChgControl()
elif hw.pmu == "axp2101":
    axp = AXP2101(i2c)
    axp.setALDO2Voltage(3300)  # LoRa VCC 3v3
    axp.setALDO3Voltage(3300)  # GPS VDD 3v3
    axp.enableALDO2()
    axp.enableALDO3()
    axp.disableTSPinMeasure()  # no battery thermistor on these boards
    axp.enableTemperatureMeasure()
    axp.enableBattDetection()
    axp.enableVbusVoltageMeasure()
    axp.enableBattVoltageMeasure()
    axp.enableSystemVoltageMeasure()
    axp.setChargingLedMode(AXP2101.XPOWERS_CHG_LED_CTRL_CHG)
else:
    print("No PMU detected (TTGO v0.7?) — relying on power-on defaults")

print("Init ok, booting...")

# --- Per-device configuration, keyed by unique id ---
dev_id = binascii.hexlify(machine.unique_id()).upper().decode()
print("Device id:", dev_id)
if dev_id not in config.DEVICE_CONFIG:
    raise Exception("No config for device id {} - add it to config.py".format(dev_id))
cfg = config.DEVICE_CONFIG[dev_id]

# --- LoRaWAN: ABP, ADR off (manual DR sweep is the whole point of the probe) ---
lw = lorawan.LoRaWAN(region=lorawan.EU868, rx2_datarate=lorawan.DR_3)
try:
    lw.nvram_restore()
    print("nvram restored - frame counter preserved")
except OSError:
    print("no saved session - provisioning ABP")
    lw.join_abp(
        dev_addr=int(cfg['DEV_ADDR'], 16),
        nwk_s_key=binascii.unhexlify(cfg['NWS_KEY']),
        app_s_key=binascii.unhexlify(cfg['APPS_KEY']),
    )
lw.adr(False)

# Custom EU868 channels 3-7 (matches the Pycom build's frequency plan)
lw.add_channel(index=3, frequency=867100000, dr_min=0, dr_max=5)
lw.add_channel(index=4, frequency=867300000, dr_min=0, dr_max=5)
lw.add_channel(index=5, frequency=867500000, dr_min=0, dr_max=5)
lw.add_channel(index=6, frequency=867700000, dr_min=0, dr_max=5)
lw.add_channel(index=7, frequency=867900000, dr_min=0, dr_max=5)

# --- Status LED: GPIO pin, "AXP" (PMU charge LED), or None ---
led_cfg = cfg.get('LED_PIN', tbeam.LED)
if led_cfg == "AXP":
    led = "AXP"
elif led_cfg is None:
    led = None
else:
    led = Pin(led_cfg, Pin.OUT)


def set_led(on):
    """Drive the status LED across its three configured forms."""
    if led is None:
        return
    if led == "AXP":
        if axp is None:
            return
        if hw.pmu == "axp192":
            axp.setChgLEDMode(axp202.AXP20X_LED_LOW_LEVEL if on else axp202.AXP20X_LED_OFF)
        else:
            axp.setChargingLedMode(AXP2101.XPOWERS_CHG_LED_ON if on else AXP2101.XPOWERS_CHG_LED_OFF)
    else:
        led.value(1 if on else 0)


# --- GPS ---
gps_pins = cfg.get('GPS_UART_PINS', (hw.gps_rx, hw.gps_tx))
gps = gps_data.GPS_data(gps_pins[0], gps_pins[1])

# Some displays (GND/VCC swapped) are powered from an IO pin.
try:
    power_display = Pin(cfg['POWER_DISPLAY'], Pin.OUT)
    power_display.value(1)
except Exception as err:
    print("No IO power needed for display:", err)

# --- Display ---
display = False
if hw.has_oled:
    try:
        data_display = DATA_display(i2c, cfg.get('ROTATE_DISPLAY', False))
        data_display.flash_message("Booting...")
        data_display.refresh()
        display = True
    except Exception as err:
        print("Display init failed:", err)

TEST_TOTALS = len(cfg['TEST_DATARATES']) * cfg['TEST_MSG_SENDS']
gps_fix = False

if display:
    data_display.flash_message("Waiting for GPS Fix")
    data_display.set_test_totals(TEST_TOTALS)


def shutdown(pin):
    print("Shutting down")
    if display:
        data_display.flash_message("Shutting Down")
        data_display.display.displayOff()
    set_led(False)
    if axp is not None:
        axp.shutdown()
    else:
        print("No PMU - cannot power off")


shutdown_pin = cfg.get('SHUTDOWN_PIN', tbeam.BUTTON)
shutdown_button = Pin(shutdown_pin, Pin.IN, Pin.PULL_UP)
shutdown_button.irq(trigger=Pin.IRQ_FALLING, handler=shutdown)


while True:
    frame_counter = 0
    gps_array, timestamp, valid = gps.get_loc()

    if gps.has_fix():
        if not gps_fix:
            if display:
                data_display.flash_message("Got GPS Fix!")
                data_display.set_loc({"latitude": gps.gps_dev.latitude[0],
                                      "longitude": gps.gps_dev.longitude[0],
                                      "altitude": gps.gps_dev.altitude,
                                      "speed": gps.gps_dev.speed[2],
                                      "hdop": gps.gps_dev.hdop,
                                      "satellites_in_use": gps.gps_dev.satellites_in_use,
                                      "satellites_in_view": gps.gps_dev.satellites_in_view})
            print("Got GPS Fix!")
            gps_fix = True
    else:
        if gps_fix:
            if display:
                data_display.flash_message("Lost GPS Fix!")
                data_display.set_loc({"latitude": 0, "longitude": 0, "altitude": 0,
                                      "speed": 0, "hdop": 99, "satellites_in_use": 0,
                                      "satellites_in_view": gps.gps_dev.satellites_in_view})
            print("Lost GPS Fix!")
            gps_fix = False

    if valid:
        if display:
            data_display.set_dr_totals(len(cfg['TEST_DATARATES']))
        for datarate in cfg['TEST_DATARATES']:
            if not valid:
                break
            if display:
                data_display.set_dr(datarate)
            print("Datarate: {}/{}".format(datarate, len(cfg['TEST_DATARATES'])))
            for test in range(cfg['TEST_MSG_SENDS']):
                gps_array, timestamp, valid = gps.get_loc()
                if not valid:
                    break
                if display:
                    data_display.set_msg_count(test)
                    data_display.set_test_count(frame_counter)
                    data_display.set_time(gps.gps_dev.timestamp)
                    data_display.set_loc({"latitude": gps.gps_dev.latitude[0],
                                          "longitude": gps.gps_dev.longitude[0],
                                          "altitude": gps.gps_dev.altitude,
                                          "speed": gps.gps_dev.speed[2],
                                          "hdop": gps.gps_dev.hdop,
                                          "satellites_in_use": gps.gps_dev.satellites_in_use,
                                          "satellites_in_view": gps.gps_dev.satellites_in_view})
                print("Test#: {}/{}".format(test + 1, cfg['TEST_MSG_SENDS']))
                print("Test Totals: {}/{}".format(frame_counter + 1, TEST_TOTALS))
                set_led(True)
                print("Sending payload: {}".format(gps_array))
                if display:
                    data_display.flash_message("Sending LoRa Packet")
                try:
                    lw.send(bytes(gps_array), port=1, datarate=datarate)
                    if display:
                        data_display.flash_message("LoRa Packet Sent")
                    print("LoRa Packet Sent")
                    pkt = lw.recv(timeout=2)
                    if pkt:
                        data, port, rssi, snr, multicast = pkt
                        if data and len(data) != 0:
                            print("Received: {}".format(data))
                            if display:
                                data_display.flash_message("Received Update")
                                data_display.set_distance(data[0])
                                data_display.set_gateway(str(data[1:], 'utf-8'))
                    lw.nvram_save()
                except OSError as err:
                    if err.args[0] == errno.EBUSY:
                        wait_ms = lw.time_until_tx()
                        print("Duty cycle restricted, waiting {} ms".format(wait_ms))
                        time.sleep_ms(wait_ms)
                    else:
                        print("LoRa Send Error: ", err)
                        if display:
                            data_display.flash_message("LoRa Send Error")
                        time.sleep(10)
                        machine.reset()
                except Exception as err:
                    print("LoRa Send Error: ", err)
                    if display:
                        data_display.flash_message("LoRa Send Error")
                    time.sleep(10)
                    machine.reset()
                set_led(False)
                frame_counter += 1
                if display:
                    data_display.flash_message("Waiting for Next Round")
                    time.sleep(0.1)
                time.sleep(config.TIME_BETWEEN_UPLINKS)

    if not valid:
        if display:
            data_display.set_loc({"latitude": 0, "longitude": 0, "altitude": 0,
                                  "speed": 0, "hdop": 99, "satellites_in_use": 0,
                                  "satellites_in_view": gps.gps_dev.satellites_in_view})
        set_led(True)
        time.sleep(0.1)
        set_led(False)
        time.sleep(0.1)

    if display:
        data_display.set_time(gps.gps_dev.timestamp)
    time.sleep(config.GPS_READ_INTERVAL)
```

- [ ] **Step 2: Syntax gate**

Run: `python3 -m py_compile main.py`
Expected: exit 0 (no `SyntaxError`; `SyntaxWarning` lines are fine).

- [ ] **Step 3: Confirm the unchanged modules still compile**

Run: `python3 -m py_compile lib/data_display.py lib/lopylcd.py lib/AXP2101.py lib/I2CInterface.py lib/micropygps.py lib/constants.py`
Expected: exit 0. (These are untouched; this is a sanity check that nothing in `main.py`'s contract broke them.)

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "Rewrite main.py for lorawan + tbeam, ABP via unique_id"
```

---

### Task 6: Update documentation

Update the two project Markdown files that describe the now-obsolete Pycom runtime: `README.md` and `CLAUDE.md`. (No `TODO.md`/`MEMORY.md` exist in the project root.) The TTN payload decoder in `README.md` is unchanged (payload format is identical) — verify it is still present and correct, do not alter it.

**Files:**
- Modify: `CLAUDE.md` (runtime/deployment/config/PMU sections)
- Modify: `README.md` (firmware target + a "Verifying the migration" checklist)

- [ ] **Step 1: Update `CLAUDE.md`**

Apply these factual corrections (edit the relevant sentences, keep the file's structure):
- "What this is": replace "running **Pycom MicroPython firmware**" with "running a custom **MicroPython firmware** with a native `lorawan` module (fork at `~/Work/esp/micropython-lorawan/`)".
- "Runtime & deployment": replace the Pycom API list with: target is custom MicroPython; LoRaWAN via `import lorawan` (`lorawan.LoRaWAN`), hardware via `import tbeam` (`tbeam.detect()`, `tbeam.i2c_bus()`, `tbeam.gps_uart()`); pins are GPIO integers, not `'Gxx'` names.
- "Configuration": `DEVICE_CONFIG` is keyed by `binascii.hexlify(machine.unique_id()).upper().decode()` (printed at boot), not `lora.mac()`. Pin overrides are optional GPIO ints defaulting to `tbeam.detect()`.
- "Architecture" step 1 (power): the AXP192/AXP2101 split is now selected by `hw.pmu` from `tbeam.detect()` (not a try/except probe); `axp202.PMU` takes an injected I2C bus.
- "Architecture" step 2 (LoRa join): `lorawan.LoRaWAN(region=EU868)` + `lw.join_abp(...)`; uplinks via `lw.send(payload, port=1, datarate=dr)`, downlinks via `lw.recv(timeout=2)`; ADR off.
- "Vendored libraries": note `axp202.py` was modified for I2C-bus injection (no longer pristine upstream).
- Update the "locally-authored code" list: `main.py`, `boot.py`, `lib/config.py`, `lib/gps_data.py`, `lib/data_display.py` (plus the now-modified `lib/axp202.py`).

- [ ] **Step 2: Add a "Verifying the migration" section to `README.md`**

Insert this section (place it after the deployment/usage instructions):

```markdown
## Verifying the migration

This firmware runs only on-device. After flashing the custom MicroPython build
and copying the files (`lib/` into the device `lib/`):

1. Boot and watch the serial console: it prints the `tbeam.detect()` result and
   the device id (`Device id: <hex>`). Add that id to `lib/config.py` with your
   ABP credentials.
2. Reboot. Confirm the PMU line matches your board (`axp192` / `axp2101`) and
   that `nvram restored` or `provisioning ABP` is printed.
3. Wait for a GPS fix — the OLED shows "Got GPS Fix!" and a position.
4. Confirm uplinks arrive on TTN at DR0/DR3/DR5; the payload decodes with the
   formatter above.
5. Plot the device on TTN Mapper.
6. Press the user button — the board powers off via the PMU.
```

- [ ] **Step 3: Verify the README payload decoder is intact**

Run: `grep -n "function Decoder\|decodeUplink\|latitude" README.md`
Expected: the existing TTN payload-formatter block is still present (it must not have been removed). Do not modify it.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "Update docs for MicroPython lorawan migration"
```

Updated files: `README.md`, `CLAUDE.md`.

---

### Task 7: On-device verification (manual)

No host execution is possible; this task is the manual acceptance check. It has no commit.

- [ ] **Step 1: Flash + deploy**

Flash the custom firmware; copy `boot.py`, `main.py` to the device root and `lib/*` into the device `lib/`.

- [ ] **Step 2: Capture the device id and provision config**

Boot, read `Device id:` from serial, add the entry to `lib/config.py`, re-copy `config.py`.

- [ ] **Step 3: Run the README "Verifying the migration" checklist**

Walk steps 2-6 of that section: PMU detected, ABP session, GPS fix, uplinks on TTN at each DR, TTN Mapper plot, shutdown button powers off.

- [ ] **Step 4: Record results**

Note any deviations (e.g. GPS UBX workaround needed, display orientation, duty-cycle backoff firing). File follow-ups if needed.

---

## Notes for the implementer

- **Do not** edit `lib/AXP2101.py`, `lib/I2CInterface.py`, `lib/constants.py`, `lib/micropygps.py`, `lib/lopylcd.py`, `lib/data_display.py` — they are already compatible. Only `lib/axp202.py` changes among the vendored/support files.
- **Credentials stay placeholders** in any commit (`"yourkeyhere"`, `"UNIQUEID"`). Never commit real keys.
- `python3 -m py_compile` emits `SyntaxWarning` for pre-existing patterns in untouched files; only a non-zero exit (real `SyntaxError`) is a failure.
- The DR sweep deliberately keeps ADR **off**; do not "fix" this to enable ADR.
