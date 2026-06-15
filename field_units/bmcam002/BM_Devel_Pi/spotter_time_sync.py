#!/usr/bin/env python3
"""
spotter_time_sync.py

Minimal Spotter/Bristlemouth UTC time helper for bmcam002.

Reads Spotter UTC time from the BM bus via the potted module serial bridge,
optionally sets the Pi system clock, converts Spotter UTC to a configured
local timezone, and decides whether the camera is inside the allowed local
transmit window.

No image capture or image transmit happens in this file.
"""

from __future__ import annotations

import datetime as dt
import os
import struct
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from zoneinfo import ZoneInfo

import serial


TOPIC = b"spotter/utc-time"


@dataclass
class CameraSchedule:
    timezone: str = "America/Los_Angeles"
    transmit_start: str = "12:00"
    transmit_end: str = "15:00"
    set_system_clock_from_spotter: bool = True
    spotter_time_timeout_seconds: int = 60
    allow_system_clock_fallback: bool = False
    uart_port: str = "/dev/ttyAMA0"
    baudrate: int = 115200


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "yes", "1", "on"}


def load_camera_schedule(path: str = "camera_schedule.yaml") -> CameraSchedule:
    """
    Tiny parser for the specific camera_schedule.yaml shape.
    Avoids adding PyYAML to the field unit.
    """
    cfg = CameraSchedule()
    if not os.path.exists(path):
        return cfg

    in_window = False
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.split("#", 1)[0].rstrip()
            if not line.strip():
                continue

            stripped = line.strip()
            if stripped == "transmit_window:":
                in_window = True
                continue

            if ":" not in stripped:
                continue

            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if in_window and key == "start":
                cfg.transmit_start = value
                continue
            if in_window and key == "end":
                cfg.transmit_end = value
                continue

            if not raw.startswith(" ") and key != "transmit_window":
                in_window = False

            if key == "timezone":
                cfg.timezone = value
            elif key == "set_system_clock_from_spotter":
                cfg.set_system_clock_from_spotter = _parse_bool(value)
            elif key == "spotter_time_timeout_seconds":
                cfg.spotter_time_timeout_seconds = int(value)
            elif key == "allow_system_clock_fallback":
                cfg.allow_system_clock_fallback = _parse_bool(value)
            elif key == "uart_port":
                cfg.uart_port = value
            elif key == "baudrate":
                cfg.baudrate = int(value)

    return cfg


def _crc16_ccitt(seed: int, data: bytes) -> int:
    crc = seed
    for b in data:
        x = ((crc >> 8) ^ b) & 0xFF
        x ^= x >> 4
        crc = ((crc << 8) ^ (x << 12) ^ (x << 5) ^ x) & 0xFFFF
    return crc


def _build_subscribe_frame_raw(topic: bytes) -> bytes:
    """
    Raw subscribe-ish frame that was field-tested on bmcam002.
    It successfully caused inbound spotter/utc-time packets to arrive through
    the custom serial_bridge firmware.
    """
    packet = bytearray()
    packet += b"\x03\x00\x00\x00"
    packet += (0).to_bytes(8, "little")
    packet += b"\x00\x00"
    packet += len(topic).to_bytes(2, "little")
    packet += topic

    crc = _crc16_ccitt(0, packet)
    packet[2] = crc & 0xFF
    packet[3] = (crc >> 8) & 0xFF
    return bytes(packet)


def _utc_from_us(utc_us: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(utc_us / 1_000_000.0, tz=dt.timezone.utc)


def _find_clock_payload(buffer: bytes) -> Optional[Tuple[int, int, dt.datetime]]:
    """
    Scan raw inbound bytes for 'spotter/utc-time' followed by an 8-byte
    little-endian uint64 timestamp in microseconds since Unix epoch.
    """
    start = 0
    while True:
        idx = buffer.find(TOPIC, start)
        if idx < 0:
            return None

        payload_start = idx + len(TOPIC)
        payload_end = payload_start + 8
        if len(buffer) < payload_end:
            return None

        payload = buffer[payload_start:payload_end]
        utc_us = struct.unpack("<Q", payload)[0]

        min_us = int(dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc).timestamp() * 1_000_000)
        max_us = int(dt.datetime(2035, 1, 1, tzinfo=dt.timezone.utc).timestamp() * 1_000_000)

        if min_us <= utc_us <= max_us:
            return idx, utc_us, _utc_from_us(utc_us)

        # Manual test payload like "test" fails plausibility; keep scanning.
        start = idx + 1


def read_spotter_utc(timeout_seconds: int = 60, port: str = "/dev/ttyAMA0", baudrate: int = 115200) -> dt.datetime:
    with serial.Serial(port, baudrate=baudrate, timeout=0.1) as ser:
        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        sub = _build_subscribe_frame_raw(TOPIC)
        ser.write(sub)
        ser.flush()

        deadline = time.time() + timeout_seconds
        buffer = bytearray()

        while time.time() < deadline:
            chunk = ser.read(256)
            if not chunk:
                continue

            buffer.extend(chunk)
            if len(buffer) > 4096:
                del buffer[: len(buffer) - 4096]

            found = _find_clock_payload(bytes(buffer))
            if found:
                _idx, _utc_us, utc_dt = found
                return utc_dt

    raise TimeoutError(f"No valid {TOPIC.decode()} message received within {timeout_seconds}s")


def set_system_clock_utc(utc_dt: dt.datetime) -> None:
    utc_dt = utc_dt.astimezone(dt.timezone.utc)
    iso = utc_dt.strftime("%Y-%m-%d %H:%M:%S")

    if os.geteuid() == 0:
        cmd = ["date", "-u", "-s", iso]
    else:
        cmd = ["sudo", "date", "-u", "-s", iso]

    subprocess.run(cmd, check=True)


def _parse_hhmm(value: str) -> dt.time:
    hh, mm = value.split(":", 1)
    return dt.time(hour=int(hh), minute=int(mm))


def is_within_local_window(utc_dt: dt.datetime, timezone_name: str, start_hhmm: str, end_hhmm: str) -> Tuple[bool, dt.datetime]:
    tz = ZoneInfo(timezone_name)
    local_dt = utc_dt.astimezone(tz)
    local_t = local_dt.time()
    start = _parse_hhmm(start_hhmm)
    end = _parse_hhmm(end_hhmm)

    if start <= end:
        allowed = start <= local_t < end
    else:
        allowed = local_t >= start or local_t < end

    return allowed, local_dt


def should_transmit_now_from_schedule(config_path: str = "camera_schedule.yaml") -> Tuple[bool, Dict[str, str]]:
    cfg = load_camera_schedule(config_path)
    info: Dict[str, str] = {"timezone": cfg.timezone, "window": f"{cfg.transmit_start}-{cfg.transmit_end}"}

    try:
        utc_dt = read_spotter_utc(
            timeout_seconds=cfg.spotter_time_timeout_seconds,
            port=cfg.uart_port,
            baudrate=cfg.baudrate,
        )
        info["source_time"] = "spotter"
        info["utc_time"] = utc_dt.isoformat()

        if cfg.set_system_clock_from_spotter:
            try:
                set_system_clock_utc(utc_dt)
                info["set_system_clock"] = "ok"
            except Exception as e:
                # Still use Spotter UTC for the window decision.
                info["set_system_clock"] = f"failed: {e}"

    except Exception as e:
        info["source_time"] = "system"
        info["spotter_time_error"] = str(e)

        if not cfg.allow_system_clock_fallback:
            info["reason"] = f"Spotter time unavailable and fallback disabled: {e}"
            return False, info

        utc_dt = dt.datetime.now(dt.timezone.utc)
        info["utc_time"] = utc_dt.isoformat()

    allowed, local_dt = is_within_local_window(
        utc_dt=utc_dt,
        timezone_name=cfg.timezone,
        start_hhmm=cfg.transmit_start,
        end_hhmm=cfg.transmit_end,
    )

    info["local_time"] = local_dt.isoformat()
    if allowed:
        info["reason"] = f"Within transmit window {cfg.transmit_start}-{cfg.transmit_end} {cfg.timezone}; local_time={local_dt.isoformat()}"
    else:
        info["reason"] = f"Outside transmit window {cfg.transmit_start}-{cfg.transmit_end} {cfg.timezone}; local_time={local_dt.isoformat()}"

    return allowed, info


if __name__ == "__main__":
    allowed, info = should_transmit_now_from_schedule("camera_schedule.yaml")
    print(f"allowed={allowed}")
    for k, v in info.items():
        print(f"{k}: {v}")
