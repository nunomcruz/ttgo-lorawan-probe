GPS_READ_INTERVAL = 0.3  # How often to read the GPS if not on the LoRaWAN network
TIME_BETWEEN_UPLINKS = 0

DEBUG=True

# Device Config
# Configuration depends on the LoRa mac address of the device
# The LoRa mac address is the key in the DEVICE_CONFIG dictionary
# The values are the LoRaWAN keys and the GPS UART pins
# The GPS UART pins are the pins that the GPS is connected to
# The GPS UART pins are different for each version of the TTGO board
# The I2C pins are used for the OLED display
# The TEST_DATARATES tuple is the datarates to test
# The TEST_MSG_SENDS is the number of tests per message size
# The TEST_TOTALS is the total number of tests
# The TEST_TOTALS is calculated from the TEST_DATARATES and TEST_MSG_SENDS


DEVICE_CONFIG = {
    "lora mac addr": {  # Device 1
        "DEV_ADDR": "yourdevaddrhere",
        "APPS_KEY": "yourkeyhere",
        "NWS_KEY": "yourkeyhere",
        "GPS_UART_PINS": ('G15', 'G12'),
        # Test Config
        # Tested datarates 0=SF12, 1=SF11, 2=SF10, 3=SF9, 4=SF8, 5=SF7
        # TEST_DATARATES=(0,1,2,3,4,5)
        "TEST_DATARATES": (0, 3, 5),
        "LED_PIN" : 'G14',
        "TEST_MSG_SENDS" : 1, # number of tests per message size
        "I2C_PINS" : ('G13', 'G2'), # For Display
        # Alternative I2C Pins, if mounted upside down
        # I2C_PINS=('G21','G22')
        "DISPLAY_ROTATE": True,
    },
    "lora mac addr 2": {   # Device 2
        "DEV_ADDR": "yourdevaddrhere",
        "APPS_KEY": "yourkeyhere",
        "NWS_KEY": "yourkeyhere",
        "GPS_UART_PINS": ('G15', 'G12'),
        # Test Config
        # Tested datarates 0=SF12, 1=SF11, 2=SF10, 3=SF9, 4=SF8, 5=SF7
        # TEST_DATARATES=(0,1,2,3,4,5)
        "TEST_DATARATES": (0, 3, 5),
        # Example for using the AXP led if no other is available
        "LED_PIN" : 'AXP',
        "TEST_MSG_SENDS" : 1, # number of tests per message size
        "I2C_PINS" : ('G13', 'G2'),  # For Display
        # Alternative I2C Pins, if mounted upside down
        # I2C_PINS=('G21','G22')
    }
}
