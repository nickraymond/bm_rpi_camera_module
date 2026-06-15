#!/usr/bin/env python3
"""
spotter_clock_probe_v3.py

Read-only Spotter UTC probe for bmcam002.

v3 fixes the subscription bug:
- Outbound subscription is official BM_SERIAL_SUB + COBS frame + 0x00.
- Inbound receive parser scans raw/decoded BM serial packets from the custom serial bridge.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import struct
import subprocess
import sys
import time
from typing import Optional, Tuple

import serial


TOPIC = b"spotter/utc-time"


def crc(seed: int, src: bytes) -> int:
    for i in src:
        e = (seed ^ i) & 0xFF
        f = e ^ ((e << 4) & 0xFF)
        seed = (seed >> 8) ^ (((f << 8) & 0xFFFF) ^ ((f << 3) & 0xFFFF)) ^ (f >> 4)
    return seed


def cobs_encode(in_bytes: bytes) -> bytes:
    final_zero = True
    out_bytes = bytearray()
    idx = 0
    search_start_idx = 0

    for in_char in in_bytes:
        if in_char == 0:
            final_zero = True
            out_bytes.append(idx - search_start_idx + 1)
            out_bytes += in_bytes[search_start_idx:idx]
            search_start_idx = idx + 1
        else:
            if idx - search_start_idx == 0xFD:
                final_zero = False
                out_bytes.append(0xFF)
                out_bytes += in_bytes[search_start_idx:idx + 1]
                search_start_idx = idx + 1
        idx += 1

    if idx != search_start_idx or final_zero:
        out_bytes.append(idx - search_start_idx + 1)
        out_bytes += in_bytes[search_start_idx:idx]

    return bytes(out_bytes)


def finalize_packet(packet: bytearray) -> bytes:
    checksum = crc(0, packet)
    packet[2] = checksum & 0xFF
    packet[3] = (checksum >> 8) & 0xFF
    return cobs_encode(packet) + b"\x00"


def build_subscribe_frame(topic: bytes) -> bytes:
    packet = bytearray.fromhex("03000000") + len(topic).to_bytes(2, "little") + topic
    return finalize_packet(packet)


def utc_from_us(utc_us: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(utc_us / 1_000_000.0, tz=dt.timezone.utc)


def format_iso_z(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def find_clock_payload(buffer: bytes) -> Optional[Tuple[int, int, dt.datetime]]:
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
            return idx, utc_us, utc_from_us(utc_us)

        start = idx + 1


def print_topic_hits(buffer: bytes) -> None:
    start = 0
    while True:
        idx = buffer.find(TOPIC, start)
        if idx < 0:
            return
        after = buffer[idx + len(TOPIC):idx + len(TOPIC) + 16]
        printable = "".join(chr(b) if 32 <= b <= 126 else "." for b in after)
        print(f"[DEBUG] saw topic at byte_offset={idx}; next16_hex={after.hex(' ')} next16_ascii={printable}")
        start = idx + 1


def set_system_clock_utc(t: dt.datetime) -> None:
    iso = t.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[CLOCK] setting system clock UTC to {iso}")
    if os.geteuid() == 0:
        cmd = ["date", "-u", "-s", iso]
    else:
        cmd = ["sudo", "-n", "date", "-u", "-s", iso]
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyAMA0")
    ap.add_argument("--baudrate", type=int, default=115200)
    ap.add_argument("--listen-seconds", type=float, default=120)
    ap.add_argument("--print-all-topics", action="store_true")
    ap.add_argument("--print-raw", action="store_true")
    ap.add_argument("--set-system-clock", action="store_true")
    ap.add_argument("--no-subscribe", action="store_true")
    args = ap.parse_args()

    print(f"[PROBE] opening UART port={args.port} baudrate={args.baudrate}")

    with serial.Serial(args.port, baudrate=args.baudrate, timeout=0.1) as ser:
        ser.reset_input_buffer()

        if not args.no_subscribe:
            frame = build_subscribe_frame(TOPIC)
            wrote = ser.write(frame)
            ser.flush()
            print(f"[PROBE] subscribed to topic='{TOPIC.decode()}' wrote={wrote} frame_bytes={len(frame)}")
            print(f"[PROBE] subscribe frame={frame.hex(' ')}")

        print(f"[PROBE] listening for {args.listen_seconds:.1f}s...")
        print("[PROBE] For manual test, run on Spotter terminal: bm pub spotter/utc-time test text 0")

        deadline = time.time() + args.listen_seconds
        buffer = bytearray()
        total_rx = 0
        printed_topic_count = 0

        while time.time() < deadline:
            chunk = ser.read(256)
            if not chunk:
                continue

            total_rx += len(chunk)
            buffer.extend(chunk)
            if len(buffer) > 4096:
                del buffer[: len(buffer) - 4096]

            if args.print_raw:
                printable = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
                print(f"[RAW] rx={len(chunk)} hex={chunk.hex(' ')} ascii={printable}")

            if args.print_all_topics:
                count = bytes(buffer).count(TOPIC)
                if count > printed_topic_count:
                    print_topic_hits(bytes(buffer))
                    printed_topic_count = count

            found = find_clock_payload(bytes(buffer))
            if found:
                idx, utc_us, t = found
                now = dt.datetime.now(dt.timezone.utc)
                drift = (t - now).total_seconds()
                print(f"[CLOCK] received topic='{TOPIC.decode()}' at buffer_offset={idx}")
                print(f"[CLOCK] utc_us={utc_us}")
                print(f"[CLOCK] decoded_utc={format_iso_z(t)}")
                print(f"[CLOCK] pi_now_utc={format_iso_z(now)}")
                print(f"[CLOCK] spotter_minus_pi_drift_seconds={drift:.3f}")

                if args.set_system_clock:
                    set_system_clock_utc(t)
                else:
                    print("[CLOCK] not setting system clock; pass --set-system-clock to enable.")

                return 0

        print(
            f"[TIMEOUT] no valid '{TOPIC.decode()}' timestamp received. "
            f"total_rx={total_rx} bytes topic_hits={bytes(buffer).count(TOPIC)}"
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
