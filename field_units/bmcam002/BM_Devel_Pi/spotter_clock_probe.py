#!/usr/bin/env python3
"""
spotter_clock_probe.py

One-shot, read-only test tool for bmcam002 / old BM_Devel_Pi camera code.

Purpose:
  - Open the Pi UART connected to the Bristlemouth serial bridge/mote.
  - Subscribe to the Spotter UTC time topic, normally: spotter/utc-time
  - Listen for published BM serial messages.
  - Decode the first 8 bytes of spotter/utc-time as little-endian uint64
    microseconds since Unix epoch UTC.
  - Print decoded UTC time and local system clock drift.

This script does NOT import or modify the production BM_Devel_Pi/bm_serial.py.
It does NOT capture images and does NOT transmit image chunks.
By default it does NOT set system time.

Typical safe test:
  cd /home/pi/BM_Devel_Pi
  /usr/bin/python3 -u spotter_clock_probe.py --listen-seconds 120

Optional system time set after you prove receive works:
  sudo /usr/bin/python3 -u spotter_clock_probe.py --listen-seconds 120 --set-system-clock

Requires:
  pip3 install pyserial
"""

from __future__ import annotations

import argparse
import os
import struct
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

try:
    import serial
except ImportError:
    print("ERROR: pyserial is not installed. Try: pip3 install pyserial", file=sys.stderr)
    raise


BM_SERIAL_PUB = 0x02
BM_SERIAL_SUB = 0x03

DEFAULT_NODE_ID = 0xC0FFEEEEF0CACC1A  # Same placeholder used in older bm_serial examples.
PLAUSIBLE_MIN_US = 946684800_000000    # 2000-01-01T00:00:00Z
PLAUSIBLE_MAX_US = 4102444800_000000   # 2100-01-01T00:00:00Z


def crc16_bm(seed: int, src: bytes) -> int:
    """CRC routine matching Bristlemouth Python serial examples."""
    for b in src:
        e = (seed ^ b) & 0xFF
        f = e ^ ((e << 4) & 0xFF)
        seed = (seed >> 8) ^ (((f << 8) & 0xFFFF) ^ ((f << 3) & 0xFFFF)) ^ (f >> 4)
    return seed & 0xFFFF


def cobs_encode(in_bytes: bytes) -> bytes:
    """COBS encoder adapted from the Sofar/Bristlemouth Python serial examples."""
    final_zero = True
    out = bytearray()
    idx = 0
    search_start_idx = 0
    for in_char in in_bytes:
        if in_char == 0:
            final_zero = True
            out.append(idx - search_start_idx + 1)
            out += in_bytes[search_start_idx:idx]
            search_start_idx = idx + 1
        else:
            if idx - search_start_idx == 0xFD:
                final_zero = False
                out.append(0xFF)
                out += in_bytes[search_start_idx : idx + 1]
                search_start_idx = idx + 1
        idx += 1
    if idx != search_start_idx or final_zero:
        out.append(idx - search_start_idx + 1)
        out += in_bytes[search_start_idx:idx]
    return bytes(out)


def cobs_decode(in_bytes: bytes) -> bytes:
    """Small COBS decoder for BM serial frames delimited by 0x00."""
    if not in_bytes:
        return b""
    out = bytearray()
    idx = 0
    n = len(in_bytes)
    while idx < n:
        code = in_bytes[idx]
        if code == 0:
            raise ValueError("COBS decode error: zero code byte inside frame")
        idx += 1
        end = idx + code - 1
        if end > n:
            raise ValueError("COBS decode error: code byte exceeds frame length")
        out += in_bytes[idx:end]
        idx = end
        if code != 0xFF and idx < n:
            out.append(0)
    return bytes(out)


def finalize_packet(packet: bytearray) -> bytes:
    """Insert CRC and return COBS-encoded BM serial frame with trailing 0x00."""
    if len(packet) < 4:
        raise ValueError("packet too short")
    packet[2] = 0
    packet[3] = 0
    checksum = crc16_bm(0, packet)
    packet[2] = checksum & 0xFF
    packet[3] = (checksum >> 8) & 0xFF
    return cobs_encode(packet) + b"\x00"


def verify_crc(packet: bytes) -> bool:
    if len(packet) < 4:
        return False
    expected = packet[2] | (packet[3] << 8)
    tmp = bytearray(packet)
    tmp[2] = 0
    tmp[3] = 0
    actual = crc16_bm(0, tmp)
    return actual == expected


def build_subscribe_frame(topic: str) -> bytes:
    topic_b = topic.encode("utf-8")
    packet = bytearray.fromhex("03000000") + len(topic_b).to_bytes(2, "little") + topic_b
    return finalize_packet(packet)


def parse_publish_packet(packet: bytes) -> Optional[Tuple[int, int, int, str, bytes]]:
    """
    Parse decoded BM_SERIAL_PUB packet.
    Returns: (node_id, message_type, version, topic, data)
    """
    if len(packet) < 4:
        return None
    msg_type = packet[0]
    if msg_type != BM_SERIAL_PUB:
        return None
    payload = packet[4:]
    if len(payload) < 12:
        return None

    node_id, pub_type, version, topic_len = struct.unpack("<QBBH", payload[:12])
    if len(payload) < 12 + topic_len:
        return None
    topic = payload[12 : 12 + topic_len].decode("utf-8", errors="replace")
    data = payload[12 + topic_len :]
    return node_id, pub_type, version, topic, data


def decode_spotter_utc(data: bytes) -> Optional[datetime]:
    """Decode first 8 bytes as little-endian uint64 epoch microseconds."""
    if len(data) < 8:
        return None
    (ts_us,) = struct.unpack("<Q", data[:8])
    if not (PLAUSIBLE_MIN_US <= ts_us <= PLAUSIBLE_MAX_US):
        return None
    return datetime.fromtimestamp(ts_us / 1_000_000, tz=timezone.utc)


def set_system_clock_utc(dt: datetime) -> None:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    iso_z = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    subprocess.run(["sudo", "date", "-u", "-s", iso_z], check=True)


def choose_port(requested: Optional[str]) -> str:
    if requested:
        return requested
    for candidate in ("/dev/ttyAMA0", "/dev/serial0", "/dev/ttyS0"):
        if os.path.exists(candidate):
            return candidate
    return "/dev/ttyAMA0"


def listen_for_clock(
    port: str,
    baudrate: int,
    topic: str,
    listen_seconds: float,
    set_system_clock: bool,
    print_all_topics: bool,
) -> int:
    print(f"[PROBE] opening UART port={port} baudrate={baudrate}", flush=True)
    with serial.Serial(port=port, baudrate=baudrate, timeout=0.1) as ser:
        # Clear stale bytes before subscribing.
        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        sub_frame = build_subscribe_frame(topic)
        written = ser.write(sub_frame)
        ser.flush()
        print(f"[PROBE] subscribed to topic='{topic}' wrote={written} frame_bytes={len(sub_frame)}", flush=True)
        print(f"[PROBE] listening for {listen_seconds:.1f}s...", flush=True)

        deadline = time.monotonic() + listen_seconds
        frame = bytearray()
        rx_frames = 0
        pub_frames = 0
        matched = 0

        while time.monotonic() < deadline:
            chunk = ser.read(256)
            if not chunk:
                continue
            for b in chunk:
                if b == 0:
                    if not frame:
                        continue
                    raw_frame = bytes(frame)
                    frame.clear()
                    rx_frames += 1
                    try:
                        decoded = cobs_decode(raw_frame)
                    except Exception as exc:
                        print(f"[PROBE][WARN] COBS decode failed: {exc}", flush=True)
                        continue

                    if not verify_crc(decoded):
                        print(f"[PROBE][WARN] CRC failed for decoded frame len={len(decoded)}", flush=True)
                        continue

                    parsed = parse_publish_packet(decoded)
                    if not parsed:
                        continue

                    pub_frames += 1
                    node_id, pub_type, version, rx_topic, data = parsed
                    if print_all_topics:
                        print(
                            f"[PUB] node=0x{node_id:016x} topic='{rx_topic}' type={pub_type} version={version} data_len={len(data)}",
                            flush=True,
                        )

                    if rx_topic != topic:
                        continue

                    matched += 1
                    dt = decode_spotter_utc(data)
                    if dt is None:
                        print(
                            f"[CLOCK][WARN] topic='{rx_topic}' data_len={len(data)} payload_hex={data.hex()}",
                            flush=True,
                        )
                        continue

                    now = datetime.now(timezone.utc)
                    drift_s = (dt - now).total_seconds()
                    print(
                        f"[CLOCK] received topic='{rx_topic}' node=0x{node_id:016x} utc={dt.isoformat()} drift={drift_s:+.3f}s data_len={len(data)}",
                        flush=True,
                    )

                    if set_system_clock:
                        print("[CLOCK] setting Linux system clock with sudo date -u -s ...", flush=True)
                        set_system_clock_utc(dt)
                        print("[CLOCK] system clock set", flush=True)
                        return 0

                    # First valid clock sample proves the subscription path works.
                    return 0
                else:
                    frame.append(b)

        print(
            f"[PROBE][TIMEOUT] no valid '{topic}' clock message received. rx_frames={rx_frames} pub_frames={pub_frames} matched_topic={matched}",
            flush=True,
        )
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Subscribe to Spotter UTC time over BM serial and print decoded clock.")
    parser.add_argument("--port", default=None, help="UART port, default auto: /dev/ttyAMA0 then /dev/serial0 then /dev/ttyS0")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--topic", default="spotter/utc-time")
    parser.add_argument("--listen-seconds", type=float, default=120.0)
    parser.add_argument("--set-system-clock", action="store_true", help="Set Linux system clock after first valid Spotter UTC message. Requires sudo privileges.")
    parser.add_argument("--print-all-topics", action="store_true", help="Print every BM publish topic seen while listening.")
    args = parser.parse_args()

    port = choose_port(args.port)
    return listen_for_clock(
        port=port,
        baudrate=args.baudrate,
        topic=args.topic,
        listen_seconds=args.listen_seconds,
        set_system_clock=args.set_system_clock,
        print_all_topics=args.print_all_topics,
    )


if __name__ == "__main__":
    raise SystemExit(main())
