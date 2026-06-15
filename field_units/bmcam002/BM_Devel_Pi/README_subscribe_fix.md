# bmcam002 Spotter clock subscribe fix

## What changed

The failing `spotter_clock_probe_v2.py` and `spotter_time_sync.py` used a raw 32-byte subscribe-ish frame.

The field diagnostic proved the correct subscription frame is the official BM_SERIAL_SUB packet:

```text
raw_sub_len: 22
raw: 03 00 7c 8c 10 00 73 70 6f 74 74 65 72 2f 75 74 63 2d 74 69 6d 65

cobs_frame_len: 24
frame: 02 03 04 7c 8c 10 11 73 70 6f 74 74 65 72 2f 75 74 63 2d 74 69 6d 65 00
```

This patch uses:

- official COBS-framed BM_SERIAL_SUB for outbound Pi -> serial_bridge subscription
- raw inbound BM serial parser for serial_bridge -> Pi messages

## Files

Replace/add:

```text
field_units/bmcam002/BM_Devel_Pi/spotter_time_sync.py
field_units/bmcam002/BM_Devel_Pi/spotter_clock_probe_v3.py
```

## Test on Pi

```bash
cd /home/pi/BM_Devel_Pi
/usr/bin/python3 -u spotter_clock_probe_v3.py --listen-seconds 90 --print-all-topics --print-raw
```

From Spotter terminal:

```text
bm pub spotter/utc-time test text 0
```

Expected Pi output includes raw bytes with:

```text
spotter/utc-timetest
```

and real clock messages such as:

```text
[CLOCK] decoded_utc=...
```

Then test schedule helper:

```bash
cd /home/pi/BM_Devel_Pi
/usr/bin/python3 -u spotter_time_sync.py
```
