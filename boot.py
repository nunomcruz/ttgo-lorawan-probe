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
