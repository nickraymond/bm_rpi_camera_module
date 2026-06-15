# bmcam002 BM command listener — development mode

This patch adds one **manual development-mode** listener:

```text
field_units/bmcam002/BM_Devel_Pi/bm_command_listener.py
```

It is not a service and it does not autostart. It only runs while you manually start it and the Pi remains powered.

## Why this exists

There are two operating modes:

1. **Development / pool testing**
   - Manually start `bm_command_listener.py`.
   - Send BM commands from the Spotter terminal.
   - Listener receives the command and calls `main_pi_camera.py` with CLI overrides.

2. **Reef scientist production**
   - Do not run the listener.
   - Cron/boot runs `main_pi_camera.py`.
   - Camera checks Spotter UTC and the configured schedule, captures/transmits if allowed, then exits.

## Topics

The listener subscribes to:

```text
nereus/bmcam002/cmd
nereus/all/cmd
```

## Start the listener on the Pi

```bash
cd /home/pi/BM_Devel_Pi
/usr/bin/python3 -u bm_command_listener.py
```

For raw debug:

```bash
cd /home/pi/BM_Devel_Pi
/usr/bin/python3 -u bm_command_listener.py --print-raw
```

For dry-run testing without actually taking a photo:

```bash
cd /home/pi/BM_Devel_Pi
/usr/bin/python3 -u bm_command_listener.py --dry-run --print-raw
```

## Send commands from the Spotter terminal

Status:

```text
bm pub nereus/bmcam002/cmd status text 0
```

Capture only, skipping the time window:

```text
bm pub nereus/bmcam002/cmd capture,transmit=0,resolution_key=480p,image_quality=20,skip_time_window=1 text 0
```

Capture and transmit, skipping the time window:

```text
bm pub nereus/bmcam002/cmd capture,transmit=1,resolution_key=480p,image_quality=20,skip_time_window=1 text 0
```

High-quality local capture only:

```text
bm pub nereus/bmcam002/cmd capture,transmit=0,resolution_key=720p,image_quality=100,skip_time_window=1 text 0
```

## How it avoids UART conflicts

The listener owns `/dev/ttyAMA0` while it is listening. When a `capture` command arrives, it closes the UART, runs `main_pi_camera.py`, then reopens the UART and subscribes again.

This matters because `main_pi_camera.py` also needs `/dev/ttyAMA0` to transmit image buffers over BM.

## What it does not do

- It does not run after a power cycle unless manually started again.
- It does not store commands while the Pi is powered off.
- It does not send ACK/status back over BM yet.
- It does not modify production boot behavior.
