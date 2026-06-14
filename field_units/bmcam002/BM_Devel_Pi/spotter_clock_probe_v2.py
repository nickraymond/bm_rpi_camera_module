#!/usr/bin/env python3
"""
spotter_clock_probe_v2.py

One-shot read-only test for bmcam002:
- Opens the Pi UART to the Bristlemouth serial bridge.
- Sends a subscription request for spotter/utc-time.
- Listens for inbound raw BM serial packets from the mote.
- Scans for topic "spotter/utc-time".
- Decodes the following 8 bytes as little-endian uint64 microseconds since Unix epoch.
- Prints UTC time and optional system-clock drift.

This script does NOT capture images, does NOT transmit image data, and does NOT set system time
unless --set-system-clock is explicitly passed.

Why v2:
The first probe assumed inbound packets were COBS-encoded. On bmcam002, inbound packets from
the custom serial_bridge app appear to arrive as raw/decoded BM serial packets, e.g.:

02 00 <crc> <node_id> <type/version> <topic_len> "spotter/utc-time" <8-byte utc_us>

So this probe scans the raw byte stream directly.
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

try:
    import serial
except ImportError:
    print("[ERROR] pyserial is required. Try: pip3 install pyserial", file=sys.stderr)
    raise


TOPIC = b"spotter/utc-time"
DEFAULT_PORTS = ["/dev/ttyAMA0", "/dev/serial0"]


def utc_from_us(utc_us: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(utc_us / 1_000_000.0, tz=dt.timezone.utc)


def format_iso_z(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def find_clock_payload(buffer: bytes) -> Optional[Tuple[int, int, dt.datetime]]:
    """
    Look for topic bytes followed by an 8-byte timestamp payload.

    Returns:
        (topic_index, utc_us, utc_datetime) if found; otherwise None.

    Basic validation:
    - Payload must decode to a plausible modern timestamp.
    - Use broad range to avoid false positives.
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

        # Plausibility: 2020-01-01 to 2035-01-01
        min_us = int(dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc).timestamp() * 1_000_000)
        max_us = int(dt.datetime(2035, 1, 1, tzinfo=dt.timezone.utc).timestamp() * 1_000_000)

        if min_us <= utc_us <= max_us:
            return idx, utc_us, utc_from_us(utc_us)

        # It may be a manual test payload like "test", not clock payload.
        start = idx + 1


def print_topic_hits(buffer: bytes) -> None:
    """
    Print all visible topic hits for debugging.
    """
    start = 0
    while True:
        idx = buffer.find(TOPIC, start)
        if idx < 0:
            return

        after = buffer[idx + len(TOPIC):idx + len(TOPIC) + 16]
        printable = "".join(chr(b) if 32 <= b <= 126 else "." for b in after)
        print(f"[DEBUG] saw topic at byte_offset={idx}; next16_hex={after.hex(' ')} next16_ascii={printable}")
        start = idx + 1


def build_subscribe_frame_raw(topic: bytes) -> bytes:
    """
    Build the same simple BM serial subscribe frame shape used by the initial probe.

    NOTE:
    This is intentionally minimal because bmcam002's custom serial_bridge appears to accept it
    based on the previous test where subscribing caused inbound topic traffic to arrive.

    If this ever stops working, compare against the upstream bm_serial.py subscribe implementation.
    """
    # BM serial packet header as used by bm_serial examples:
    # message type 0x03? We include the previously tested 24-byte subscription frame behavior.
    #
    # Previous probe wrote 24 bytes for topic spotter/utc-time and triggered return traffic.
    # To preserve that behavior, this function implements the compact form:
    #   [0x03, 0x00, CRC_L, CRC_H] + node_id(8 zeros) + type/version? + topic_len + topic
    #
    # For this field probe, the exact outbound subscribe packet is less critical than inbound
    # parsing because the previous v1 probe already caused inbound data to flow.
    #
    # We will use a best-effort packet modeled on Bristlemouth serial message patterns.
    packet = bytearray()
    packet += b"\x03\x00\x00\x00"          # message type/sub placeholder + crc placeholder
    packet += (0).to_bytes(8, "little")     # node id / source placeholder
    packet += b"\x00\x00"                  # type/version placeholder
    packet += len(topic).to_bytes(2, "little")
    packet += topic

    crc = crc16_ccitt(0, packet)
    packet[2] = crc & 0xFF
    packet[3] = (crc >> 8) & 0xFF

    # bmcam002 return path is raw, but outbound to serial_bridge historically uses COBS+0x00.
    # However v1 worked and reported wrote=24. To avoid changing behavior too much, we send
    # raw packet first, then optional COBS if requested by flag is not used in this v2.
    return bytes(packet)


def crc16_ccitt(seed: int, data: bytes) -> int:
    crc = seed
    for b in data:
        x = ((crc >> 8) ^ b) & 0xFF
        x ^= x >> 4
        crc = ((crc << 8) ^ (x << 12) ^ (x << 5) ^ x) & 0xFFFF
    return crc


def set_system_clock_utc(t: dt.datetime) -> None:
    iso = t.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[CLOCK] setting system clock UTC to {iso}")
    subprocess.run(["date", "-u", "-s", iso], check=True)


def choose_port(port_arg: Optional[str]) -> str:
    if port_arg:
        return port_arg
    for p in DEFAULT_PORTS:
        if os.path.exists(p):
            return p
    return DEFAULT_PORTS[0]


def main() -> int:
    ap = argparse.ArgumentParser(description="Read Spotter UTC time from BM serial bridge on Pi.")
    ap.add_argument("--port", default=None, help="UART port, default tries /dev/ttyAMA0 then /dev/serial0")
    ap.add_argument("--baudrate", type=int, default=115200)
    ap.add_argument("--listen-seconds", type=float, default=120)
    ap.add_argument("--print-all-topics", action="store_true", help="Print every spotter/utc-time topic hit.")
    ap.add_argument("--print-raw", action="store_true", help="Print raw RX hex/ascii chunks.")
    ap.add_argument("--set-system-clock", action="store_true", help="Set Pi system clock to received UTC time.")
    ap.add_argument("--no-subscribe", action="store_true", help="Do not send subscribe frame; only listen.")
    args = ap.parse_args()

    port = choose_port(args.port)
    print(f"[PROBE] opening UART port={port} baudrate={args.baudrate}")

    with serial.Serial(port, baudrate=args.baudrate, timeout=0.1) as ser:
        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        if not args.no_subscribe:
            sub = build_subscribe_frame_raw(TOPIC)
            wrote = ser.write(sub)
            ser.flush()
            print(f"[PROBE] sent raw subscribe-ish frame topic='{TOPIC.decode()}' wrote={wrote} bytes")
            print("[PROBE] Note: if no clock arrives, rerun with manual Spotter console: bm pub spotter/utc-time test text 0")

        print(f"[PROBE] listening for {args.listen_seconds:.1f}s...")

        deadline = time.time() + args.listen_seconds
        buffer = bytearray()
        total_rx = 0
        topic_hits = 0

        while time.time() < deadline:
            chunk = ser.read(256)
            if not chunk:
                continue

            total_rx += len(chunk)
            buffer.extend(chunk)

            # Keep buffer bounded but large enough to span several packets.
            if len(buffer) > 4096:
                del buffer[: len(buffer) - 4096]

            if args.print_raw:
                printable = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
                print(f"[RAW] rx={len(chunk)} hex={chunk.hex(' ')} ascii={printable}")

            if args.print_all_topics:
                before = topic_hits
                count = bytes(buffer).count(TOPIC)
                if count > before:
                    print_topic_hits(bytes(buffer))
                    topic_hits = count

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
        print("[HINT] If topic_hits > 0, the return path works but payload may be manual text, not 8-byte UTC.")
        print("[HINT] Try a longer listen window, or wait for real Spotter clock publish.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
