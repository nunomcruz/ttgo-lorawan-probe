# ttgo-lorawan-probe
LoRaWAN Probe
This is a simple LoRaWAN probe that sends multiple messages at different datarates to test the range of a LoRaWAN network.
It uses the GPS to get a location and sends this in the message.
Supports TTGO T-Beam with Pycom Firmware and OLED display.

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
5. Configure settings in lib/config.py, including your newly created device at TTN
6. Push everything to the TTGO
7. Wait for the messages to arrive at TTN
8. Check the data in your integration and push it to TTN Mapper
9. Use the data to create a map of the range of your network
10. Profit!
