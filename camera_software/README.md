# 🐠 Underwater Raspberry Pi Camera with Bristlemouth

This repository contains the source code and configuration files for an underwater Raspberry Pi camera powered by Bristlemouth hardware. The project supports image capture, logging, compression, and communication over serial. It's designed for both field use and development.

---

## 📦 Quick Start Options

### ✅ Wire up the BM Dev Kit + Pi + Camera
![](/Users/nickraymond/PycharmProjects/RPi_Camera_Module/camera_software/BM Camera Wiring.png)

### ✅ Use the Prebuilt SD Card Image 

Download the full disk image [link TBD] and flash it to an SD card using [Balena Etcher](https://etcher.balena.io/) or Raspberry Pi Imager. This ensures:

- Pre-installed libraries
- Pre-configured camera settings
- Built-in Wi-Fi hotspot (`bmcam000`)
- SSH enabled

```bash
SSID: bmcam000
Password: (none)
SSH login: pi / raspberry
```

You can then connect to the Pi over SSH:
```bash
ssh pi@192.168.4.1
```

---

## 🔄 Updating the Software

If you're using the full disk image, you can still pull the latest code:

```bash
cd ~/bm_rpi_camera_module
git pull origin main
```

This will fetch updates to the codebase without affecting your system settings.

---

## 📷 Camera Behavior on Boot

By default, the Pi captures a single image **60 seconds after power on**. This is managed using `crontab`:

```bash
crontab -e
```

You’ll see:
```bash
@reboot sleep 60 && /usr/bin/python3 /home/pi/bm_rpi_camera_module/camera_software/main_pi_camera.py
```

You can modify this to change the delay or add recurring captures.

---

## Testing the Camera

Test the camera connection using the included script:

```bash
cd ~/bm_rpi_camera_module/camera_software/examples
python3 camera_test.py
```

Successful output will show `Image captured and saved as 'image_VGA.jpg'` in the terminal. If not, check the ribbon cable connection to the camera.

---

## Project Architecture

### Main Script: `main_pi_camera.py`
Handles:
- Time retrieval (RTC or system clock)
- Image capture & compression
- CPU temperature readout
- Logging and UART communication

### Helper Modules:
- `process_image_v2.py`: Capture, compress, and buffer image
- `read_CPU_temp.py`: Get Pi CPU temp
- `save_image.py`: Save to disk
- `split_and_send.py`: Chunk and transmit images
- `log_update.py`: Record logs (size, time, temp)

### Example/Test Scripts:
- `camera_test.py`: Quick test image capture
- `uart_test.py`: Test UART connectivity
- `bm_serial_example.py`: Example Bristlemouth serial logic

---

## ⚙️ Configuration Options

- `USE_RTC` (in `main_pi_camera.py`): Use external RTC if available
- `time_start`, `time_end`: Set operational hours (24h format)

You can change these directly in the Python source for now.

---

## 🔧 First Boot Config (For Custom SD Images)

Inside `boot_config_files/`, you’ll find:
- `hostname`: Sets Pi hostname (default: `bmcam000`)
- `wpa_supplicant.conf`: Preload Wi-Fi creds (optional)
- `ssh`: Enable SSH on first boot
- `userconf`: Set default username/password

Copy these into the **boot** partition before first boot to auto-configure the device.

---

## Contributing

Contributions are welcome!

- Fork the repo
- Create a feature branch
- Submit a pull request with clear description and test results

---

## 📄 License

This project is licensed under the **Apache License 2.0**. You’re free to use, modify, and distribute it with attribution. See [`LICENSE`](LICENSE) for full details.

---

## 📬 Contact

Have questions or want to contribute hardware integrations? Open an issue or contact Nick Raymond via the [Bristlemuth forums](https://bristlemouth.discourse.group/).

---

