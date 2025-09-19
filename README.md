# BM Camera — daemon + plug-in camera modules (short guide)

## What this does

* **`bm_daemon`** is a small background service that listens on the Bristlemouth bus for commands (topics) and runs handlers.
* Camera logic lives in a **separate, modular package** (`bm_camera`). Others can add new plug-ins later without touching the core daemon.

---

## Quick setup (with Wi-Fi fallback + low-power tweaks)

1. On your Pi, from the project folder, run the setup script (uses `hostapd`/`dnsmasq` for fallback hotspot and applies headless/camera tweaks):

```bash
sudo chmod +x setup_bm_rpi.sh
sudo ./setup_bm_rpi.sh <hostname> <ap-ssid> <ap-pass> --disable-usb --disable-hdmi --force-dhcpcd
# example:
sudo ./setup_bm_rpi.sh bmcam000 BM-Camera-AP "StrongPass123" --disable-usb --disable-hdmi --force-dhcpcd
```

**How Wi-Fi fallback works:**

* On boot the Pi first tries to join your normal Wi-Fi (use `/etc/wpa_supplicant/wpa_supplicant.conf` to store your SSID/PSK).
* A small boot-time check waits \~30s; **if internet is reachable → stay in client mode**.
* If not, it starts a **hotspot on wlan0** (`<ap-ssid>`, WPA2) at **192.168.50.1/24** and serves DHCP so you can connect to the Pi.

---

## Running the daemon

### Dev mode (foreground)

From the project root:

```bash
python -m bm_daemon.agent
```

You should see it log the topics it subscribed to (e.g., `camera/capture/image`, `camera/capture/video`, plus `spotter/utc-time` for RTC if configured).

### As a background service (systemd)

Create a simple unit:

```bash
sudo tee /etc/systemd/system/bm-daemon.service >/dev/null <<'EOF'
[Unit]
Description=BM Daemon
After=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/bm_rpi_camera_module
ExecStart=/usr/bin/python3 -m bm_daemon
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now bm-daemon
sudo journalctl -u bm-daemon -f
```
What to check:
```
# is it set to start at boot?
systemctl is-enabled bm-daemon

# is it currently running?
systemctl status bm-daemon

# follow logs
journalctl -u bm-daemon -f
```

If you didn’t run the enable step yet, do:
```
sudo systemctl daemon-reload
sudo systemctl enable --now bm-daemon
```

To stop it from starting at boot later:
```
sudo systemctl disable --now bm-daemon
```
---

## How it’s structured 

* **Core (`bm_daemon`)**

  * Starts the bus, loads config (`config.yaml`), registers **core handlers** (e.g., RTC), and loads **plug-ins** listed under `plugins:`.
  * Passes a shared `ctx` (e.g., bus handle, config) to handlers.

* **Plug-ins (`bm_camera` today; more later)**

  * Each handler module exposes:

	* `topics = ["some/topic"]`
	* `def handle(msg, *, ctx): ...` where `msg = {"node","topic","data"}`
  * Add more modules (e.g., `bm_light`, `bm_quickRelease`) and list them in `config.yaml → plugins:` to extend behavior without editing the core.

---

## Using the camera topics

### Topics

* **Images:** `camera/capture/image`
  Flags:
  `res=<key>` (e.g., 1080p), `fmt=<jpeg|heif>`, `q=<1..100>`, `send=<0|1>`
  Saves locally; optionally transmits via Spotter when `send=1`.

* **Video:** `camera/capture/video`
  Flags:
  `dur=<Xs|Yms>`, `res=<key>`, `fps=<int>`, `br=<e.g., 2M>`
  Saves locally; **no transmission** for video (bandwidth/cost).

### 💾 How you use it

* **Default (no send):** → captures & encodes, **no transmit**, status shows `tx=no`.

  ```
  bm pub camera/capture/image res=1080p text 0
  ```

* **Explicitly send:** → same pipeline + **transmit via Spotter**, status shows `tx=yes`.

  ```
  bm pub camera/capture/image res=1080p,send=1 text 0
  ```

* **Force JPEG with quality 60, still no send:**

  ```
  bm pub camera/capture/image fmt=jpeg,q=60 text 0
  ```

* **Take a video:**

  ```
  bm pub camera/capture/video dur=3s,res=720p,fps=25,br=2M text 0
  ```

> Captured files are written under the paths defined in `config.yaml` (e.g., `images/`, `videos/`). Status messages are published back on the configured status topic.

---

## Adding your own plug-in later

Create a new package (e.g., `bm_light/handlers/…`), implement `topics` + `handle(msg, *, ctx)`, and add the module path to `config.yaml → plugins:`. Restart the daemon—no core changes needed.

That’s it. If anything doesn’t start, check logs with `journalctl -u bm-daemon -f` or run in the foreground to see detailed errors.
