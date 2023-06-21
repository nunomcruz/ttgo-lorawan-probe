"""
LoRaWAN Probe
This is a simple LoRaWAN probe that sends multiple messages at different datarates
to test the range of a LoRaWAN network.
It uses the GPS to get a location and sends this in the message.
It also sends a counter so that the messages can be identified.
Supports TTGO T-Beam with Pycom Firmware and OLED display

@author Nuno Cruz aka nunomcruz
"""

import os
import time
import socket
import json
import binascii
import config
import struct
import uos
import sys
#import gc

from data_display import DATA_display
from network import LoRa, WLAN
from machine import Timer, I2C, Pin
import axp202

import gps_data

#init AXP
try:
    axp = axp202.PMU(address=axp202.AXP192_SLAVE_ADDRESS)
    axp.setLDO2Voltage(3300)   # T-Beam LORA VDD   3v3
    axp.setLDO3Voltage(3300)   # T-Beam GPS  VDD    3v3
    axp.enablePower(axp202.AXP192_LDO3)
    axp.enablePower(axp202.AXP192_LDO2)
    axp.enableADC(axp202.AXP202_ADC1, axp202.AXP202_VBUS_VOL_ADC1)
    axp.enableADC(axp202.AXP202_ADC1, axp202.AXP202_VBUS_CUR_ADC1)
    axp.enableADC(axp202.AXP202_ADC1, axp202.AXP202_BATT_VOL_ADC1)
    axp.enableADC(axp202.AXP202_ADC1, axp202.AXP202_BATT_CUR_ADC1)
    axp.setChgLEDChgControl()
except Exception as err:
    print("AXP Not Available, probably a TTGO < 1: ", err)


#gc.enable()
#chrono = Timer.Chrono() #Keep track of time since boot so can  record how long between GPS readings
#chrono.start()
last_gps_reading = 0    #When the last GPS reading was taken
wlan = WLAN()
wlan.deinit()


print("Init ok, booting...")

#lora = LoRa(mode=LoRa.LORAWAN)
lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.EU868, bandwidth=LoRa.BW_125KHZ, coding_rate=LoRa.CODING_4_8, tx_power=20)
lora.nvram_restore()
lora.add_channel(index=3, frequency=867100000, dr_min=0, dr_max=5)
lora.add_channel(index=4, frequency=867300000, dr_min=0, dr_max=5)
lora.add_channel(index=5, frequency=867500000, dr_min=0, dr_max=5)
lora.add_channel(index=6, frequency=867700000, dr_min=0, dr_max=5)
lora.add_channel(index=7, frequency=867900000, dr_min=0, dr_max=5)

#Single SF channel-DR6/SF7
#lora.add_channel(index=8, frequency=868300000, dr_min=6, dr_max=6)


lora_mac = binascii.hexlify(lora.mac()).upper().decode()

dev_addr = config.DEVICE_CONFIG[lora_mac]['DEV_ADDR']
nwk_swkey = binascii.unhexlify(config.DEVICE_CONFIG[lora_mac]['NWS_KEY'])
app_swkey = binascii.unhexlify(config.DEVICE_CONFIG[lora_mac]['APPS_KEY'])
lora.join(activation=LoRa.ABP, auth=(dev_addr, nwk_swkey, app_swkey))
#lora.join(activation=LoRa.OTAA, auth=(dev_ota_eui, app_eui, app_ota_key), timeout=0, dr=0)


sock = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
sock.setsockopt(socket.SOL_LORA, socket.SO_DR, 0)
sock.setblocking(True)
sock.bind(1)

led = Pin(config.DEVICE_CONFIG[lora_mac]['LED_PIN'], Pin.OUT)

gps = gps_data.GPS_data(config.DEVICE_CONFIG[lora_mac]['GPS_UART_PINS'])

i2c = I2C(1, pins=config.DEVICE_CONFIG[lora_mac]['I2C_PINS'])

try:
    data_display = DATA_display(i2c)
    data_display.flash_message("Booting...")
    data_display.refresh()
    display = True
except Exception as err:
    print("Display Not Avaliable, probably not installed: ", err)
    display = False


valid = False
frame_counter = 0
gps_fix = False


TEST_TOTALS = len(config.DEVICE_CONFIG[lora_mac]['TEST_DATARATES'])*config.DEVICE_CONFIG[lora_mac]['TEST_MSG_SENDS']

if display:
    data_display.flash_message("Waiting for GPS Fix")
    data_display.set_test_totals(TEST_TOTALS)


while True:
    frame_counter = 0
    # start off with a garbaged collected memory
    #gc.collect()
    gps_array, timestamp, valid = gps.get_loc()
    #gps_array = [183, 30, 136, 121, 132, 158, 0, 118, 33, 2]
    #gps_array = [183, 30, 144, 121, 132, 122, 0, 98, 61, 5]

    if gps.has_fix():
        if gps_fix == False:
            if display:
                data_display.flash_message("Got GPS Fix!")
                data_display.set_loc({"latitude":gps.gps_dev.latitude[0], "longitude":gps.gps_dev.longitude[0]})
            print("Got GPS Fix!")
            gps_fix = True
                #data_display.set_timestamp(gps.gps_dev.date_string())
    else:
        if gps_fix == True:
            if display:
                data_display.flash_message("Lost GPS Fix!")
            print("Lost GPS Fix!")
            gps_fix = False

    if valid:
        # received valid output
        if display:
            data_display.set_dr_totals(len(config.DEVICE_CONFIG[lora_mac]['TEST_DATARATES']))
        for datarate in config.DEVICE_CONFIG[lora_mac]['TEST_DATARATES']:
            if not valid:
                print("No Fix Datarate Loop")
                break
            if display:
                data_display.set_dr(datarate)
            print("Datarate: {}/{}".format(datarate,len(config.DEVICE_CONFIG[lora_mac]['TEST_DATARATES'])))
            sock.setsockopt(socket.SOL_LORA, socket.SO_DR, datarate)
            for test in range(config.DEVICE_CONFIG[lora_mac]['TEST_MSG_SENDS']):
                print("Consuming GPS at Test Loop")
                gps_array, timestamp, valid = gps.get_loc()
                print("Done")
                if not valid:
                    print("No Fix at Test Loop")
                    break
                if display:
                    data_display.set_msg_count(test)
                    data_display.set_test_count(frame_counter)
                    data_display.set_time(gps.gps_dev.timestamp)
                    data_display.set_loc({"latitude":gps.gps_dev.latitude[0], "longitude":gps.gps_dev.longitude[0]})
                print("Test#: {}/{}".format(test+1,config.DEVICE_CONFIG[lora_mac]['TEST_MSG_SENDS']))
                print("Test Totals: {}/{}".format(frame_counter+1,TEST_TOTALS))
                led.value(1)
                print("Sending payload: {}".format(gps_array))
                if display:
                    data_display.flash_message("Sending LoRa Packet")
                try:
                    sock.send(bytes(gps_array))
                    if display:
                        data_display.flash_message("LoRa Packet Sent")
                    print("LoRa Packet Sent")
                except Exception as err:
                    print("LoRa Send Error: ", err)
                    if display:
                        data_display.flash_message("LoRa Send Error")
                        time.sleep(10)
                        machine.reset()
                led.value(0)
                frame_counter+=1
                print("Waiting for Next Round")
                if display:
                    data_display.flash_message("Waiting for Next Round")
                    time.sleep(0.1)
                time.sleep(config.TIME_BETWEEN_UPLINKS)
            #print("Consuming GPS at Datarate Loop")
            #gps_array, timestamp, valid = gps.get_loc()
            #print("Done")
    if not valid:
        led.value(1)
        time.sleep(0.1)
        led.value(0)
        time.sleep(0.1)
    #GPS Sleep
    if display:
        data_display.set_time(gps.gps_dev.timestamp)
    time.sleep(config.GPS_READ_INTERVAL)
