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
