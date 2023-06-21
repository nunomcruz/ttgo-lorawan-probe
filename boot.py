import machine
import os
import time
import config

known_nets = {
    # SSID : PSK (passphrase)
    'KNOWN_SSID_NETWORK': 'PASSWORD',
} # change this dict to match your WiFi settings

# disable these two lines if you don't want serial access
uart = machine.UART(0, 115200)
os.dupterm(uart)

# test needed to avoid losing connection after a soft reboot
if machine.reset_cause() != machine.SOFT_RESET:
    from network import WLAN
    wl = WLAN()

    # save the default ssid and auth
    #original_ssid = wl.ssid()
    #original_auth = wl.auth()

    wl.mode(WLAN.STA)

    for ssid, bssid, sec, channel, rssi in wl.scan():
        # Note: could choose priority by rssi if desired
        try:
            print("Connecting to %s" %(ssid))
            wl.connect(ssid, (sec, known_nets[ssid]), timeout=10000)
            break
        except KeyError:
            pass # unknown SSID
    else:
        print("Providing AP for access")
        wl.init(mode=WLAN.AP, ssid='tbeam_debug', auth=(WLAN.WPA2, 'RANDOMPASSWORD'), channel=1, antenna=WLAN.INT_ANT)
#If you want to use WiFi don't forget to comment WiFi denit on main.py
