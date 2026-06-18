# bmcam002 Spotter UTC Schedule Wrapper Patch

This zip contains complete replacement files for the bmcam002 legacy app folder:

- `spotter_time_sync.py`
- `camera_schedule.yaml`
- `run_capture_cycle.sh`
- `README_BMCAM002_SCHEDULE_PATCH.md`

It intentionally does **not** change `bm_serial.py`, image chunking, or the legacy capture/transmit path.

## Behavior

On each production run:

```text
read camera_schedule.yaml
subscribe to spotter/utc-time over UART
receive Spotter UTC from Bristlemouth
optionally set the Pi system clock from Spotter UTC
convert UTC to configured local timezone
check local transmit window
capture/transmit only if inside the window
exit cleanly if outside the window
```

The production command must not include `--skip-time-window`:

```bash
cd /home/pi/BM_Devel_Pi
/usr/bin/python3 -u main_pi_camera.py --transmit
```

Manual test override only:

```bash
cd /home/pi/BM_Devel_Pi
/usr/bin/python3 -u main_pi_camera.py --transmit --resolution-key 480p --image-quality 20 --skip-time-window
```

## Install on bmcam002

Copy the zip to the Pi, then:

```bash
cd /home/pi/BM_Devel_Pi
mkdir -p /home/pi/BM_Devel_Pi_backup_$(date +%Y%m%d_%H%M%S)
cp -a spotter_time_sync.py camera_schedule.yaml run_capture_cycle.sh README_BMCAM002_SCHEDULE_PATCH.md /home/pi/BM_Devel_Pi_backup_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || true
```

From the unzipped folder, copy files into place:

```bash
cp spotter_time_sync.py camera_schedule.yaml run_capture_cycle.sh README_BMCAM002_SCHEDULE_PATCH.md /home/pi/BM_Devel_Pi/
chmod +x /home/pi/BM_Devel_Pi/run_capture_cycle.sh
```

## Allow cron to set Linux time from Spotter UTC

`spotter_time_sync.py` uses `sudo -n date ...` when not running as root.
Install this sudoers rule once:

```bash
sudo tee /etc/sudoers.d/nereus-date >/dev/null <<'EOF'
pi ALL=(root) NOPASSWD: /usr/bin/date
EOF

sudo chmod 440 /etc/sudoers.d/nereus-date
sudo visudo -cf /etc/sudoers.d/nereus-date
```

Expected:

```text
/etc/sudoers.d/nereus-date: parsed OK
```

## Test schedule only

```bash
cd /home/pi/BM_Devel_Pi
/usr/bin/python3 -u spotter_time_sync.py
```

Closed window success looks like:

```text
allowed=False
source_time: spotter
set_system_clock: ok
reason: Outside transmit window ...
```

Open window success looks like:

```text
allowed=True
source_time: spotter
set_system_clock: ok
reason: Within transmit window ...
```

## Test production app path

```bash
cd /home/pi/BM_Devel_Pi
/usr/bin/python3 -u main_pi_camera.py --transmit
```

## Test wrapper manually

```bash
cd /home/pi/BM_Devel_Pi
/usr/bin/flock -n /tmp/bmcam002_capture.lock /home/pi/BM_Devel_Pi/run_capture_cycle.sh
```

Inspect the latest log:

```bash
tail -n 200 "$(ls -t /home/pi/BM_Devel_Pi/cron_logs/capture_cycle_*.log | head -1)"
```

## Install @reboot cron

Use this if the power controller boots the Pi once per intended capture cycle:

```bash
crontab -l > /home/pi/crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null || true
crontab -l 2>/dev/null | grep -v 'run_capture_cycle.sh' > /tmp/bmcam002_cron || true
echo '@reboot /usr/bin/flock -n /tmp/bmcam002_capture.lock /home/pi/BM_Devel_Pi/run_capture_cycle.sh' >> /tmp/bmcam002_cron
crontab /tmp/bmcam002_cron
crontab -l
```

Use a repeating cron instead if the Pi stays powered all day:

```cron
*/30 * * * * /usr/bin/flock -n /tmp/bmcam002_capture.lock /home/pi/BM_Devel_Pi/run_capture_cycle.sh
```

The app-level schedule gate still prevents capture/transmit outside the configured window.

## Configuration examples

San Francisco development, 8 AM to 3 PM:

```yaml
timezone_preset: "sf"
transmit_window:
  start: "08:00"
  end: "15:00"
image:
  resolution_key: "720p"
  image_quality: 25
```

Reef production, noon to 3 PM:

```yaml
timezone_preset: "sf"
transmit_window:
  start: "12:00"
  end: "15:00"
image:
  resolution_key: "720p"
  image_quality: 25
```
