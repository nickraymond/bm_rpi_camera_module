# bmcam002 potted camera field guide

This folder contains the field-tested potted camera code for `bmcam002`.

## Current mission-safe behavior

At the start of each camera cycle, `main_pi_camera.py` can subscribe to Spotter UTC time on the Bristlemouth bus before it takes an image.

The subscription is sent from the Pi to the potted mote as an official `BM_SERIAL_SUB` packet, COBS framed and terminated with `0x00`. The topic is:

```text
spotter/utc-time
```

The potted mote forwards matching BM bus messages back to the Pi UART. The Pi decodes the raw inbound `spotter/utc-time` payload as a little-endian `uint64` timestamp in microseconds since Unix epoch. The code then:

1. Converts Spotter UTC into the configured local timezone.
2. Checks the configured local transmit window.
3. Continues capture/transmit only if the local time is inside that window.
4. Fails closed if Spotter time is unavailable and fallback is disabled.

The legacy local `Within Window` field still exists in the old code path, but it is kept permissive. The Spotter UTC schedule is the intended deployment gate.

## Schedule and image defaults

Edit this file on the Pi for deployment defaults:

```bash
nano /home/pi/BM_Devel_Pi/camera_schedule.yaml
```

Current testing default:

```yaml
timezone: "America/Los_Angeles"
enforce_spotter_time_window: true

transmit_window:
  start: "12:00"
  end: "15:00"

image:
  resolution_key: "720p"
  image_quality: 25
```

For manual one-off tests outside the schedule, use the CLI flag:

```bash
--skip-time-window
```

This is called a **CLI flag** because it is a boolean command-line switch. In the YAML file, `enforce_spotter_time_window` is the equivalent configuration variable.

## Useful timezones

Use IANA timezone names.

| Region | Timezone |
|---|---|
| Hawaii | `Pacific/Honolulu` |
| US West Coast / California | `America/Los_Angeles` |
| US East Coast / Florida Keys | `America/New_York` |
| Australia East Coast / Sydney | `Australia/Sydney` |
| Australia West Coast / Perth | `Australia/Perth` |

For Florida Keys deployment, use:

```yaml
timezone: "America/New_York"
```

## Image quality convention

The image quality value is encoder quality, not compression amount.

| Value | Meaning |
|---:|---|
| `0` | lowest image quality, most compression, smallest file |
| `25` | current field default |
| `100` | highest image quality, least compression, largest file |

For bandwidth-constrained field testing:

```text
15 = aggressive compression / small diagnostic image
25 = recommended field default
40 = better quality / larger payload
60+ = likely large unless resolution is small
100 = least compressed / largest encoded file
```

The current HEIC/JPEG path always encodes the image. `image_quality=100` is the least-compressed supported mode in this code path; it is not raw/uncompressed image output.

## Resolution presets

The IMX708 sensor and current camera path support both wide 16:9-style presets and cropped/taller 4:3-style presets.

### 16:9 presets

Use these when the goal is to keep roughly the same wide scene/FOV while reducing pixel density, file size, and transmission time.

| Key | Size | Use |
|---|---:|---|
| `native_12mp` | 4608x2592 | Native IMX708 16:9-style full frame |
| `12MP` | 4608x2592 | Alias for native 12MP |
| `4k` | 3840x2160 | High detail, large files |
| `2.7k` | 2704x1520 | High detail, smaller than 4K |
| `1296p` | 2304x1296 | Native-looking 16:9 test size |
| `1080p` | 1920x1080 | Standard HD |
| `720p` | 1280x720 | Current recommended field default |
| `480p` | 854x480 | Bandwidth-constrained test |
| `360p` | 640x360 | Very small diagnostic image |

### 4:3 presets

Use these if intentionally cropping to a narrower/taller view. This may be useful with the IMX708 and wide lens if the outer image edges show stronger barrel distortion. Cropping the edge regions can reduce distortion, file size, transmit time, and energy use.

| Key | Size | Use |
|---|---:|---|
| `4_3_full_crop` | 3456x2592 | Tall/full 4:3 crop |
| `4_3_8mp` | 3264x2448 | High-detail 4:3 |
| `8MP` | 3264x2448 | Alias for 4:3 8MP |
| `4_3_5mp` | 2592x1944 | Medium/high 4:3 |
| `5MP` | 2592x1944 | Alias for 4:3 5MP |
| `4_3_3mp` | 2048x1536 | Medium 4:3 |
| `4_3_2mp` | 1600x1200 | Smaller 4:3 |
| `4_3_1080` | 1440x1080 | 4:3 HD-style test |
| `XGA` | 1024x768 | Small 4:3 field test |
| `SVGA` | 800x600 | Very small 4:3 |
| `VGA` | 640x480 | Smallest diagnostic 4:3 |

For same scene with smaller files, prefer:

```text
1080p → 720p → 480p → 360p
```

For cropped/taller framing to reduce edge distortion, test:

```text
4_3_1080 → XGA → VGA
```

## Commands

### Test Spotter UTC schedule only

```bash
cd /home/pi/BM_Devel_Pi
/usr/bin/python3 -u spotter_time_sync.py
```

### Capture only, using YAML defaults

```bash
cd /home/pi/BM_Devel_Pi
/usr/bin/python3 -u main_pi_camera.py
```

### Capture and transmit, using YAML defaults

```bash
cd /home/pi/BM_Devel_Pi
/usr/bin/python3 -u main_pi_camera.py --transmit
```

### Capture only with local CLI overrides

```bash
/usr/bin/python3 -u main_pi_camera.py --resolution-key 480p --image-quality 20 --skip-time-window
```

### Capture and transmit with local CLI overrides

```bash
/usr/bin/python3 -u main_pi_camera.py --transmit --resolution-key 480p --image-quality 20 --skip-time-window
```

### Least-compressed supported encoded image test

```bash
/usr/bin/python3 -u main_pi_camera.py --resolution-key 720p --image-quality 100 --skip-time-window
```

Check the file size before transmitting high-quality images.
