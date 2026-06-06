# ttgo-lorawan-probe
LoRaWAN Probe
This is a simple LoRaWAN probe that sends multiple messages at different datarates to test the range of a LoRaWAN network.
It uses the GPS to get a location and sends this in the message.
Supports TTGO T-Beam with a custom MicroPython firmware (fork at `~/Work/esp/micropython-lorawan/`) and OLED display.

# Instructions
1. Create your app at TTN, use the following sample as payload formatter:

```javascript
function decodeUplink(input) {
  var bytes = input.bytes;
  var port = input.fPort;
  var decoded = {};
  if(port == 1) {
    if(bytes.length == 10) {
      decoded.gpsfix = true;
      decoded.latitude = ((bytes[0]<<16)>>>0) + ((bytes[1]<<8)>>>0) + bytes[2];
      decoded.latitude = (decoded.latitude / 16777215.0 * 180) - 90;
      decoded.longitude = ((bytes[3]<<16)>>>0) + ((bytes[4]<<8)>>>0) + bytes[5];
      decoded.longitude = (decoded.longitude / 16777215.0 * 360) - 180;
      var altValue = ((bytes[6]<<8)>>>0) + bytes[7];
      var sign = bytes[6] & (1 << 7);
      if(sign){
        decoded.altitude = 0xFFFF0000 | altValue;
      }else{
        decoded.altitude = altValue;
      }
      decoded.hdop = bytes[8] / 10.0;
      decoded.sats = bytes[9];
    } 
  }
  if (decoded.latitude == -90) {
    decoded = {};
    decoded.gpsfix = false;
  }

  return {
      data: decoded
    };
}
```
2. Create a device in your app
3. Configure the device to use OTAA or ABP, ABP is better for testing range
4. Configure an integration to store your received data together with network metrics (rssi and snr)
5. Configure settings: copy `lib/config.example.py` to `lib/config.py` and add
   your device. `lib/config.py` is gitignored so credentials never reach the repo
6. Push everything to the TTGO
7. Wait for the messages to arrive at TTN
8. Check the data in your integration and push it to TTN Mapper
9. Use the data to create a map of the range of your network
10. Profit!

## Verifying the migration

This firmware runs only on-device. After flashing the custom MicroPython build
and copying the files (`lib/` into the device `lib/`):

1. Boot and watch the serial console: it prints the `tbeam.detect()` result and
   the device id (`Device id: <hex>`). Copy `lib/config.example.py` to
   `lib/config.py` and add that id with your ABP credentials. Pin overrides use
   GPIO integers (e.g. `14`), not Pycom `'Gxx'` strings.
2. Reboot. Confirm the PMU line matches your board (`axp192` / `axp2101`) and
   that `nvram restored` or `provisioning ABP` is printed.
3. Wait for a GPS fix — the OLED shows "Got GPS Fix!" and a position.
4. Confirm uplinks arrive on TTN at DR0/DR3/DR5; the payload decodes with the
   formatter above.
5. Plot the device on TTN Mapper.
6. Press the user button — the board powers off via the PMU.
