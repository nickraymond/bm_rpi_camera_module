
# Camera Triggers via BM (handlers)

New handlers:
- `bm_agent/handlers/camera_still.py`  → topic `topics.camera_still`
- `bm_agent/handlers/camera_video.py`  → topic `topics.camera_video`

## 1) Configure topics

Edit `camera_software/bm_agent/config.yaml` (create if missing) and add:

```yaml
uart_device: /dev/serial0
baudrate: 115200
topics:
  rtc: spotter/utc-time
  camera_still: camera/still/capture
  camera_video: camera/video/capture
clock:
  enabled: true
  apply_if_drift_seconds: 2
  min_apply_interval_seconds: 300
```

## 2) Run the agent

```bash
python /home/pi/bm_camera/camera_software/bm_agent/run_agent.py
```

## 3) Bench test from the Pi (no cell)

In another terminal, publish to the topics:

```bash
# Still @ 1080p (no transmit)
python /home/pi/bm_camera/camera_software/bm_agent/tools/publish.py camera/still/capture --json '{"resolution":"1080p","transmit":false}'

# Video @ 720p 3s @ ~3 Mbps
python /home/pi/bm_camera/camera_software/bm_agent/tools/publish.py camera/video/capture --json '{"resolution":"720p","duration_s":3,"fps":30,"bitrate":3000000,"transmit":false}'
```

Files appear under:
- Stills: `<project>/camera_software/images/` (from `process_image.IMAGE_DIRECTORY`)
- Videos: `<project>/camera_software/videos/` (from `video_capture.VIDEO_DIRECTORY`)
```
