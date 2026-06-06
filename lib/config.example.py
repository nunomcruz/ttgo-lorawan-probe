# Per-device configuration for the LoRaWAN probe — TEMPLATE.
#
# Copy this file to lib/config.py and fill in real values.
# lib/config.py is gitignored so credentials never reach the repo.
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
