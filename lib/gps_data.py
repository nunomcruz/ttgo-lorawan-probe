# gps_data.py
# Wrapper around microGPS.py
# Changes by nunomcruz: added sats to payload, added bug correction for TTGO V1.1 GPS

from micropygps import MicropyGPS
from machine import UART
import array
import config
import time


class GPS_data():

    def __init__(self,uart_pins):
        self.uart = UART(1, 9600, pins=uart_pins)
        time.sleep(0.5)
        self.gps_dev = MicropyGPS(location_formatting='dd')
        # Bug correction for TTGO V1.1 GPS - https://github.com/nunomcruz/ttgo-tbeam-gps-reset-python
        if not self.uart.any():
            if config.DEBUG:
                print("Fixing GPS issue not receiving data")
            self.uart.write(b'\xb5b\x06\x00\x14\x00\x01\x00\x00\x00\xd0\x08\x00\x00\x80%\x00\x00\x07\x00\x03\x00\x00\x00\x00\x00\xa2\xb5') # Set GPS to 9600 baud
            time.sleep(1.5)
            if self.uart.any():
                if config.DEBUG:
                    print("GPS issue fixed")
            else:
                raise Exception("GPS issue not fixed")

    def convert_payload(self, lat, lon, alt, hdop, sats):
        """
            Converts to the format used by ttnmapper.org
        """
        payload = []
        latb = int(((float(lat) + 90) / 180) * 0xFFFFFF)
        lonb = int(((float(lon) + 180) / 360) * 0xFFFFFF)
        altb = int(round(float(alt), 0))
        hdopb = int(float(hdop) * 10)

        payload.append(((latb >> 16) & 0xFF))
        payload.append(((latb >> 8) & 0xFF))
        payload.append((latb & 0xFF))
        payload.append(((lonb >> 16) & 0xFF))
        payload.append(((lonb >> 8) & 0xFF))
        payload.append((lonb & 0xFF))
        payload.append(((altb  >> 8) & 0xFF))
        payload.append((altb & 0xFF))
        payload.append(hdopb & 0xFF)
        # Add number of satellites to payload
        payload.append(sats & 0xFF)
        return payload

    def get_loc(self):
        coords = array.array('B', [0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        timestamp = (0, 0, 0)
        valid = False
        sentence = ''
        #time.sleep(0.1)
        while self.uart.any():
            sentence = self.uart.readline()
            if sentence == None:
                return coords, timestamp, valid
            # if timed-out process last line
            if len(sentence) > 0:
                for x in sentence:
                    #print("Char: ", hex(x))
                    try:
                        self.gps_dev.update(chr(x))
                    except Exception as err:
                        print("Exception: ", err)
                if config.DEBUG:
                    print(sentence)
                    print('Longitude', self.gps_dev.longitude)
                    print('Latitude', self.gps_dev.latitude)
                    print('UTC Timestamp:', self.gps_dev.timestamp)
                    print('Fix Status:', self.gps_dev.fix_stat)
                    print('Altitude:', self.gps_dev.altitude)
                    print('Horizontal Dilution of Precision:', self.gps_dev.hdop)
                    print('Satellites in Use by Receiver:', self.gps_dev.satellites_in_use)
        if self.has_fix():
            valid = True
            timestamp = self.gps_dev.timestamp
            latitude=self.gps_dev.latitude[0]
            if self.gps_dev.latitude[1] == 'S':
                latitude=latitude*-1
            longitude=self.gps_dev.longitude[0]
            if self.gps_dev.longitude[1] == 'W':
                longitude=longitude*-1
            coords = self.convert_payload(latitude, longitude, self.gps_dev.altitude, self.gps_dev.hdop, self.gps_dev.satellites_in_use)
        return coords, timestamp, valid

    def has_fix(self):
        return (self.gps_dev.fix_stat > 0 and self.gps_dev.latitude[0] > 0)
