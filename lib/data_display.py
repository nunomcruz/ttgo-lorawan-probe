# data_display.py
# Class which updates the display in 2 ways
# * refresh_timestamp: update UTC GPS received time each second
# * refresh_all: update entire display by calling refresh_data
# uses:
#   lopylcd:    a simplified i2c 128x64 display driver
#   config:     global application parameters
#
import lopylcd
import _thread
import time


class DATA_display:

    timestamp = "00:00:00"
    message = "LoRaWAN Survey"
    default_message = message
    flash_count = 0
    refresh_lock = 0
    dr = 0
    dr_totals = 0
    msg_size = 0
    msg_count = 0
    msg_totals = 0
    test_count = 0
    test_totals = 0
    payload = 0
    payload_totals = 0
    latitude = 0
    longitude = 0
    hour = 0
    minute = 0
    second = 0


    def _th_refresh(self):
        while True:
            #print('Running refresh thread')
            self.refresh()
            time.sleep(5)

    def __init__(self, i2c):
        self.refresh_lock = _thread.allocate_lock()
        self.display = lopylcd.lopylcd(i2c)
        self.display.set_contrast(255)
        self.display.displayOn()
        self.refresh_all(self.dr, self.dr_totals, self.msg_size, self.msg_count, self.msg_totals, self.test_count, self.test_totals, self.payload, self.payload_totals, self.latitude, self.longitude, self.hour, self.minute, self.second)
        #_thread.start_new_thread(self._th_refresh,())


    def refresh_all(self, dr, dr_totals, msg_size, msg_count, msg_totals, test_count, test_totals, payload, payload_totals, latitude, longitude, hour, minute, second):
        self.dr = dr
        self.dr_totals = dr_totals
        self.msg_size = msg_size
        self.msg_count = msg_count
        self.msg_totals = msg_totals
        self.test_count = test_count
        self.test_totals = test_totals
        self.payload = payload
        self.payload_totals = payload_totals
        self.latitude = float(latitude)
        self.longitude = float(longitude)
        self.hour = int(hour)
        self.minute = int(minute)
        self.second = float(second)
        self.refresh()

    def refresh(self):
        if self.display.isConnected():
            with self.refresh_lock:
                #self.display.command(self.display.SSD1306_LEFT_HORIZONTAL_SCROLL)
                #self.display.command(self.display.SSD1306_LEFT_HORIZONTAL_SCROLL)
                self.display.command(0x00)
                self.display.command(0x00) #start
                self.display.command(0X00)
                self.display.command(0x00) #end 0x0f -> 16 rows -> scroll completo
                self.display.command(0X00)
                self.display.command(0XFF)

                self.display.clearBuffer()
                if self.flash_count > 0:
                    self.flash_count-=1
                else:
                    self.message = self.default_message
                self.display.addString(0, 0, "{:^21}".format(self.message))
                self.display.addString(0, 1, "{:^21}".format("---------------------")) #21 chars total
                self.display.addString(0, 2, "Time:    {:02d}:{:02d}:{:06.3f}".format(self.hour,self.minute,self.second))
                #self.display.addString(0, 3, "Payload#:       {:2d}/{:2d}".format(self.payload,self.payload_totals))
                #self.display.addString(0, 4, "Payload Size:    {:2d} B".format(self.msg_size))
                self.display.addString(0, 5, "DR: {:2d} Totals {:2d}".format(self.dr,self.dr_totals))
                self.display.addString(0, 6, "Test Count:    {:2d}/{:2d}".format(self.test_count,self.test_totals))
                self.display.addString(0, 7, "Coords: {:6.3f},{:6.3f}".format(self.latitude,self.longitude))
                #self.display.command(self.display.SSD1306_DEACTIVATE_SCROLL)
                self.display.drawBuffer()
                #self.display.command(self.display.SSD1306_ACTIVATE_SCROLL)

        else:
            print("Error: LCD not found")

    def flash_message(self, message):
        self.message = message
        self.flash_count = 2
        self.refresh()

    def set_dr(self,dr):
        self.dr = dr
        self.refresh()

    def set_dr_totals(self,dr_totals):
        self.dr_totals = dr_totals
        self.refresh()

    def set_time(self,time):
        self.hour = time[0]
        self.minute = time[1]
        self.second = time[2]
        #self.display.addString(0, 2, "Time:    {:02d}:{:02d}:{:06.3f}".format(self.hour,self.minute,self.second))
        #self.display.drawBuffer()
        self.refresh()

    def set_loc(self, loc):
        self.latitude = float(loc["latitude"])
        self.longitude = float(loc["longitude"])
        self.refresh()

    def set_msg_size(self,msg_size):
        self.msg_size = msg_size
        self.refresh()

    def set_msg_count(self,msg_count):
        self.msg_count = msg_count
        self.refresh()

    def set_msg_totals(self,msg_totals):
        self.msg_totals = msg_totals
        self.refresh()

    def set_test_count(self,test_count):
        self.test_count = test_count
        self.refresh()

    def set_test_totals(self,test_totals):
        self.test_totals = test_totals
        self.refresh()

    def set_payload(self,payload):
        self.payload = payload
        self.refresh()

    def set_payload_totals(self,payload_totals):
        self.payload_totals = payload_totals
        self.refresh()
