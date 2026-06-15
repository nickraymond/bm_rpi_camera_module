# bmcam002 reef camera field notes

This folder tracks the lightweight potted-camera code used for bmcam002 field testing and reef shipment.

## Current scope

The production path intentionally stays small:

- Use the existing `main_pi_camera.py`, `process_image_v2.py`, and `bm_serial.py` capture/transmit flow.
- Subscribe to Spotter UTC time at the start of each cycle.
- Use Spotter UTC converted into a configured local timezone to decide whether capture/transmit is allowed.
- Keep the proven Bristlemouth transmit path: `BUFFER_SIZE = 300` and network byte `x01` in `bm_serial.py`.

## Spotter UTC time gate

At the start of each camera cycle, `main_pi_camera.py` calls `spotter_time_sync.py`.

The time-sync helper does the following:

1. Opens the Pi UART to the potted Bristlemouth serial bridge.
2. Sends an official `BM_SERIAL_SUB` subscription for `spotter/utc-time`.
   - The outbound subscribe packet is COBS-framed and terminated with `0x00`.
   - The known-good frame for `spotter/utc-time` is 24 bytes.
3. Receives raw/decoded BM serial publish packets from the custom serial bridge.
4. Finds the `spotter/utc-time` topic.
5. Decodes the following 8-byte little-endian timestamp as microseconds since Unix epoch.
6. Optionally sets the Pi system clock from Spotter UTC.
7. Converts Spotter UTC to the configured local timezone.
8. Allows capture/transmit only if the local time is inside the configured window.

If Spotter time is unavailable and `allow_system_clock_fallback: false`, the system fails closed and skips capture/transmit.

## Configuration file

Runtime defaults live in:

```text
/home/pi/BM_Devel_Pi/camera_schedule.yaml
```

Tracked source copy:

```text
field_units/bmcam002/BM_Devel_Pi/camera_schedule.yaml
```

Example:

```yaml
timezone: "America/Los_Angeles"

transmit_window:
  start: "12:00"
  end: "15:00"

image:
  resolution_key: "720p"
  image_quality: 25

set_system_clock_from_spotter: true
spotter_time_timeout_seconds: 60
allow_system_clock_fallback: false

uart_port: "/dev/ttyAMA0"
baudrate: 115200
```

### Common timezones

Use IANA timezone names.

| Region | Timezone |
|---|---|
| Hawaii | `Pacific/Honolulu` |
| US West Coast / San Francisco / Los Angeles | `America/Los_Angeles` |
| US East Coast / Florida Keys | `America/New_York` |
| Australia East Coast, Sydney/Melbourne | `Australia/Sydney` |
| Australia East Coast, Queensland / Brisbane | `Australia/Brisbane` |
| Australia West Coast / Perth | `Australia/Perth` |
| UTC testing | `UTC` |

For Florida Keys deployment, use:

```yaml
timezone: "America/New_York"
```

## Image quality convention

The system uses `image_quality`, following the standard encoder convention used by HEIC/JPEG tools:

```text
0   = lowest image quality / most compression / smallest file
25  = good bandwidth-constrained field default
40  = better image quality, larger payload
100 = highest image quality / least compression / largest file
```

Do not interpret `image_quality = 100` as maximum compression. It is the opposite: highest quality and largest file.

## Resolution presets

`process_image_v2.py` defines the valid `resolution_key` values.

### 16:9 presets

Use these when the goal is to keep roughly the same wide scene/FOV while reducing pixel density, file size, transmit time, and energy use.

| Key | Size | Notes |
|---|---:|---|
| `native_12mp` | 4608x2592 | IMX708 native 16:9-style full sensor output |
| `12MP` | 4608x2592 | Legacy alias for `native_12mp` |
| `4k` | 3840x2160 | High detail, large files |
| `2.7k` | 2704x1520 | High detail, smaller than 4K |
| `1296p` | 2304x1296 | Good high-detail 16:9 test size |
| `1080p` | 1920x1080 | Standard HD |
| `720p` | 1280x720 | Recommended field default |
| `480p` | 854x480 | Bandwidth-constrained field test |
| `360p` | 640x360 | Very small diagnostic image |

For same scene with smaller files, test in this order:

```text
1080p → 720p → 480p → 360p
```

### 4:3 presets

Use these if intentionally cropping to a narrower/taller view. This can be useful with a wide lens and IMX708 if the outer image edges show stronger barrel distortion. Cropping edge regions can reduce distortion, file size, transmit time, and energy use.

| Key | Size | Notes |
|---|---:|---|
| `4_3_full_crop` | 3456x2592 | Tall/full 4:3 crop from IMX708 height |
| `4_3_8mp` | 3264x2448 | High-detail 4:3 |
| `8MP` | 3264x2448 | Legacy alias for `4_3_8mp` |
| `4_3_5mp` | 2592x1944 | Medium/high 4:3 |
| `5MP` | 2592x1944 | Legacy alias for `4_3_5mp` |
| `4_3_3mp` | 2048x1536 | Medium 4:3 |
| `4_3_2mp` | 1600x1200 | Smaller 4:3 |
| `4_3_1080` | 1440x1080 | 4:3 HD-style test |
| `XGA` | 1024x768 | Small 4:3 field test |
| `SVGA` | 800x600 | Very small 4:3 |
| `VGA` | 640x480 | Smallest diagnostic 4:3 |

For cropped/taller framing to reduce edge distortion, test:

```text
4_3_1080 → XGA → VGA
```

## How to run

Run from the production folder on the Pi:

```bash
cd /home/pi/BM_Devel_Pi
```

### Clock/window test only

```bash
/usr/bin/python3 -u spotter_time_sync.py
```

Expected output includes:

```text
allowed=True/False
source_time: spotter
utc_time: ...
local_time: ...
reason: ...
```

### Capture only, no transmit

This checks Spotter time, checks the configured local window, captures an image if allowed, logs the result, but does not transmit image buffers.

```bash
/usr/bin/python3 -u main_pi_camera.py
```

### Capture and transmit

This checks Spotter time, checks the configured local window, captures, encodes, splits into 300-byte buffers, and transmits over the proven legacy x01 path.

```bash
/usr/bin/python3 -u main_pi_camera.py --transmit
```

### Override resolution for one run

```bash
/usr/bin/python3 -u main_pi_camera.py --resolution-key 480p
```

### Override image quality for one run

```bash
/usr/bin/python3 -u main_pi_camera.py --image-quality 20
```

### Override both and transmit

```bash
/usr/bin/python3 -u main_pi_camera.py --transmit --resolution-key 480p --image-quality 20
```

CLI arguments override `camera_schedule.yaml` for that one run only. They do not edit the config file.

## Deployment defaults

For local San Francisco testing:

```yaml
timezone: "America/Los_Angeles"
image:
  resolution_key: "720p"
  image_quality: 25
```

For Florida Keys deployment:

```yaml
timezone: "America/New_York"
image:
  resolution_key: "720p"
  image_quality: 25
```
