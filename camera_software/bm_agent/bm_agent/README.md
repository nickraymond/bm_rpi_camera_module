# BM Agent (Raspberry Pi) — RTC/LED Dispatcher

A small service that listens on the Bristlemouth bus (UART `/dev/serial0`), subscribes to topics, and dispatches actions:

- `spotter/utc-time` → log UTC time + **optionally set Pi system clock** (safe, throttled)
- `camera/led` → turn an LED on/off (payload `0x01`/`0x00` or `"on"`/`"off"`)

## Requirements

- Raspberry Pi OS (Bullseye/Bookworm)
- Hardware UART enabled, serial login disabled
- User in `dialout` group
- Internet (for `git clone` and package installs)

### Enable UART (one-time)

```bash
sudo raspi-config
# Interface Options → Serial Port
#  - Login shell over serial?  → No
#  - Enable serial port hardware? → Yes
sudo reboot
```

### After reboot

```bash
ls -l /dev/serial0              # should exist
groups $USER                    # should include 'dialout'
# if not:
sudo usermod -a -G dialout $USER && sudo reboot
````

If a serial console is running:

```bash
sudo systemctl disable --now serial-getty@ttyAMA0.service || true
sudo systemctl disable --now serial-getty@ttyS0.service || true
```

### Quick Install
```bash
# Choose a directory name and branch if needed
bash <(curl -fsSL https://raw.githubusercontent.com/YOUREPO/YOURPATH/install_bm_agent.sh) \
  --repo https://github.com/YOUREPO/YOUR_REPO.git \
  --branch add_bm_RTC_service \
  --name bm_camera
```

The script will:

- clone/update the repo into ~/bm_camera
- create a Python venv, install deps (pyserial, pyyaml, RPi.GPIO)
- install bm-set-time helper + sudoers entry
- write a default config.yaml if missing
- install and start the bm-agent.service

### Config

Edit ~/bm_camera/camera_software/bm_agent/config.yaml:
```yaml
uart_device: /dev/serial0
baudrate: 115200

topics:
  rtc: "spotter/utc-time"
  led: "camera/led"

led:
  pin: 17

clock:
  enabled: true
  max_backward_seconds: 0
  apply_if_drift_seconds: 2
  min_apply_interval_seconds: 300
```

### Service Control
```bash
# stop / start / restart
sudo systemctl stop bm-agent.service
sudo systemctl start bm-agent.service
sudo systemctl restart bm-agent.service

# status (summary)
sudo systemctl status bm-agent.service

# logs (live)
sudo journalctl -u bm-agent.service -f

# confirm system clock (UTC)
date -u
```

### How to Add a New Topic (example: LED)

1. Update config.yaml:
```yaml
topics:
  led: "camera/led"
led:
  pin: 17
```
2. Implement handler in bm_agent/handlers/led.py.
3. Register in bm_agent/dispatcher.py.
4. Restart service:
```bash
sudo systemctl restart bm-agent.service
```
### Troubleshooting

- /dev/serial0 busy
Stop services and check owner:

```bash
sudo systemctl stop bm-agent.service
sudo lsof /dev/serial0
sudo fuser -v /dev/serial0
```


- No logs
Use sudo with journalctl:
```bash
sudo journalctl -u bm-agent.service -f
```

- Clock not updating
Check drift thresholds in config.yaml. Ensure sudoers:
```bash
sudo visudo -c
cat /etc/sudoers.d/bm-set-time    # should allow NOPASSWD for /usr/local/sbin/bm-set-time
```