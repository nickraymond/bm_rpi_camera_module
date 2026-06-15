#!/usr/bin/env python3
"""
bm_command_listener.py

Development-only BM bus command listener for bmcam002.

Use case:
- Manually run this while the Pi is powered during pool / bench testing.
- It subscribes to BM command topics via the potted serial_bridge.
- It listens for simple text commands published on the BM bus.
- When it receives a capture command, it closes the UART and calls main_pi_camera.py
  with CLI overrides such as --resolution-key, --image-quality, --transmit,
  and --skip-time-window.
- After the camera command finishes, it reopens the UART, resubscribes, and keeps listening.

Important:
- This is NOT installed as a service.
- It does NOT run after a Pi power cycle unless you manually start it again.
- It does NOT change production cron/boot behavior.
- It prints status locally to the SSH console; it does not send command ACKs back over BM yet.

Known-good Bristlemouth behavior used here:
- Outbound subscribe uses official BM_SERIAL_SUB, COBS-framed, with 0x00 terminator.
- Inbound publishes from this potted module arrive as raw/decoded BM serial packets.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import serial


DEFAULT_TOPICS = [
    "nereus/bmcam002/cmd",
    "nereus/all/cmd",
]


@dataclass
class CommandMessage:
    topic: str
    payload: str
    raw_payload: bytes


# ---------------------------------------------------------------------------
# Bristlemouth serial subscribe helpers
# ---------------------------------------------------------------------------

def bm_crc(seed: int, src: bytes) -> int:
    """CRC used by the Bristlemouth serial Python examples."""
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
    checksum = bm_crc(0, packet)
    packet[2] = checksum & 0xFF
    packet[3] = (checksum >> 8) & 0xFF
    return cobs_encode(packet) + b"\x00"


def build_subscribe_frame(topic: str) -> bytes:
    topic_b = topic.encode("utf-8")
    packet = bytearray.fromhex("03000000") + len(topic_b).to_bytes(2, "little") + topic_b
    return finalize_packet(packet)


def subscribe_topics(ser: serial.Serial, topics: Iterable[str]) -> None:
    for topic in topics:
        frame = build_subscribe_frame(topic)
        wrote = ser.write(frame)
        ser.flush()
        print(f"[LISTENER] subscribed topic='{topic}' wrote={wrote} frame_bytes={len(frame)}")


# ---------------------------------------------------------------------------
# Raw inbound parser
# ---------------------------------------------------------------------------

def printable_ascii(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b <= 126 else "." for b in data)


def extract_messages(buffer: bytes, topics: List[str]) -> List[CommandMessage]:
    """
    Extract command messages from raw/decoded inbound BM serial publish packets.

    Observed raw packet shape from bmcam002:
      02 00 <crc_le_u16> <node_id_8> <type_u8> <version_u8>
      <topic_len_le_u16> <topic> <payload>

    Packets are not separated with a terminator on inbound UART, so payload is
    treated as bytes until the next raw publish packet marker 02 00 or buffer end.
    Command payloads should be ASCII text.
    """
    msgs: List[CommandMessage] = []

    # Work by finding known topic strings. This is robust for our command topics
    # and avoids needing a full BM packet parser.
    for topic in topics:
        topic_b = topic.encode("utf-8")
        start = 0
        while True:
            idx = buffer.find(topic_b, start)
            if idx < 0:
                break

            payload_start = idx + len(topic_b)

            # Find next apparent BM_SERIAL_PUB packet start after payload_start.
            # This prevents duplicated packets in one read from merging payloads.
            next_packet = buffer.find(b"\x02\x00", payload_start)
            if next_packet < 0:
                payload = buffer[payload_start:]
            else:
                payload = buffer[payload_start:next_packet]

            # Strip common whitespace/null padding. Command payloads are text.
            payload = payload.strip(b"\x00\r\n\t ")

            if payload:
                try:
                    payload_text = payload.decode("utf-8", errors="replace").strip()
                except Exception:
                    payload_text = repr(payload)
                msgs.append(CommandMessage(topic=topic, payload=payload_text, raw_payload=payload))

            start = idx + 1

    return msgs


# ---------------------------------------------------------------------------
# Command parsing/execution
# ---------------------------------------------------------------------------

def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_command_payload(payload: str) -> Tuple[str, Dict[str, str]]:
    """
    Parse payloads like:
      capture,transmit=1,resolution_key=480p,image_quality=20,skip_time_window=1
      status
      help
    """
    text = payload.strip()

    # Support either comma-separated or whitespace-separated first token.
    if "," in text:
        parts = [p.strip() for p in text.split(",") if p.strip()]
    else:
        parts = [p.strip() for p in shlex.split(text) if p.strip()]

    if not parts:
        return "", {}

    command = parts[0].lower()
    kv: Dict[str, str] = {}

    for part in parts[1:]:
        if "=" not in part:
            kv[part.lower()] = "1"
            continue
        key, value = part.split("=", 1)
        kv[key.strip().lower()] = value.strip()

    return command, kv


def build_camera_command(kv: Dict[str, str], python_bin: str, camera_script: str) -> List[str]:
    cmd = [python_bin, "-u", camera_script]

    transmit = parse_bool(kv.get("transmit", "0"))
    if transmit:
        cmd.append("--transmit")

    resolution_key = kv.get("resolution_key") or kv.get("resolution-key") or kv.get("resolution")
    if resolution_key:
        cmd += ["--resolution-key", resolution_key]

    image_quality = kv.get("image_quality") or kv.get("image-quality") or kv.get("quality")
    if image_quality:
        cmd += ["--image-quality", str(int(image_quality))]

    skip_time_window = parse_bool(
        kv.get("skip_time_window", kv.get("skip-time-window", kv.get("skip_window", "0")))
    )
    if skip_time_window:
        cmd.append("--skip-time-window")

    return cmd


def print_help() -> None:
    print("[LISTENER] Supported BM command payloads:")
    print("  status")
    print("  help")
    print("  capture,transmit=0,resolution_key=480p,image_quality=20,skip_time_window=1")
    print("  capture,transmit=1,resolution_key=480p,image_quality=20,skip_time_window=1")
    print("")
    print("[LISTENER] Example Spotter commands:")
    print("  bm pub nereus/bmcam002/cmd status text 0")
    print("  bm pub nereus/bmcam002/cmd capture,transmit=0,resolution_key=480p,image_quality=20,skip_time_window=1 text 0")
    print("  bm pub nereus/bmcam002/cmd capture,transmit=1,resolution_key=480p,image_quality=20,skip_time_window=1 text 0")


def command_fingerprint(msg: CommandMessage) -> str:
    h = hashlib.sha1()
    h.update(msg.topic.encode("utf-8"))
    h.update(b"\x00")
    h.update(msg.raw_payload)
    return h.hexdigest()


def run_camera_command(cmd: List[str], dry_run: bool) -> int:
    print(f"[LISTENER] running: {' '.join(shlex.quote(c) for c in cmd)}")
    if dry_run:
        print("[LISTENER] dry-run enabled; not executing camera command")
        return 0
    result = subprocess.run(cmd)
    print(f"[LISTENER] camera command exit_code={result.returncode}")
    return result.returncode


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def listen_once(
    port: str,
    baudrate: int,
    topics: List[str],
    listen_seconds: Optional[float],
    python_bin: str,
    camera_script: str,
    dedupe_seconds: float,
    dry_run: bool,
    print_raw: bool,
    recent: Dict[str, float],
) -> bool:
    """
    Returns True to continue listener loop, False to stop.
    """
    with serial.Serial(port, baudrate=baudrate, timeout=0.1) as ser:
        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        subscribe_topics(ser, topics)

        print("[LISTENER] listening for BM commands...")
        print_help()

        deadline = None if listen_seconds is None or listen_seconds <= 0 else time.time() + listen_seconds
        buffer = bytearray()

        while True:
            if deadline is not None and time.time() > deadline:
                print("[LISTENER] listen timeout reached")
                return False

            chunk = ser.read(512)
            if not chunk:
                continue

            if print_raw:
                print(f"[RAW] rx={len(chunk)} hex={chunk.hex(' ')} ascii={printable_ascii(chunk)}")

            buffer.extend(chunk)
            if len(buffer) > 8192:
                del buffer[: len(buffer) - 8192]

            msgs = extract_messages(bytes(buffer), topics)
            if not msgs:
                continue

            for msg in msgs:
                fp = command_fingerprint(msg)
                now = time.time()

                if fp in recent and (now - recent[fp]) < dedupe_seconds:
                    continue
                recent[fp] = now

                print(f"[LISTENER] received topic='{msg.topic}' payload='{msg.payload}'")

                command, kv = parse_command_payload(msg.payload)
                if command in {"", "noop"}:
                    continue

                if command == "status":
                    print("[LISTENER] status: alive")
                    continue

                if command == "help":
                    print_help()
                    continue

                if command == "capture":
                    camera_cmd = build_camera_command(kv, python_bin=python_bin, camera_script=camera_script)

                    # IMPORTANT: close UART before launching camera script because main_pi_camera.py
                    # needs /dev/ttyAMA0 for BM transmit.
                    print("[LISTENER] capture command received; closing listener UART before camera run")
                    # Return special instruction to caller via exception-free path.
                    # We cannot run while 'with ser' is open; store command in function attr.
                    listen_once.pending_camera_cmd = camera_cmd
                    return True

                print(f"[LISTENER][WARN] unknown command='{command}' payload='{msg.payload}'")


listen_once.pending_camera_cmd = None  # type: ignore[attr-defined]


def main() -> int:
    parser = argparse.ArgumentParser(description="Development BM command listener for bmcam002.")
    parser.add_argument("--port", default="/dev/ttyAMA0")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument(
        "--topic",
        action="append",
        default=None,
        help="BM command topic to subscribe to. Can be repeated. Defaults to bmcam002 and all topics.",
    )
    parser.add_argument(
        "--listen-seconds",
        type=float,
        default=0,
        help="How long to listen. 0 means run until Ctrl+C.",
    )
    parser.add_argument("--python-bin", default="/usr/bin/python3")
    parser.add_argument("--camera-script", default="/home/pi/BM_Devel_Pi/main_pi_camera.py")
    parser.add_argument("--dedupe-seconds", type=float, default=10.0)
    parser.add_argument("--dry-run", action="store_true", help="Print camera command but do not execute it.")
    parser.add_argument("--print-raw", action="store_true")
    args = parser.parse_args()

    topics = args.topic if args.topic else DEFAULT_TOPICS
    recent: Dict[str, float] = {}

    print("[LISTENER] bmcam002 development BM command listener")
    print("[LISTENER] This is manual/dev mode only; Ctrl+C to stop.")
    print(f"[LISTENER] topics={topics}")

    try:
        while True:
            listen_once.pending_camera_cmd = None  # type: ignore[attr-defined]

            should_continue = listen_once(
                port=args.port,
                baudrate=args.baudrate,
                topics=topics,
                listen_seconds=args.listen_seconds,
                python_bin=args.python_bin,
                camera_script=args.camera_script,
                dedupe_seconds=args.dedupe_seconds,
                dry_run=args.dry_run,
                print_raw=args.print_raw,
                recent=recent,
            )

            camera_cmd = getattr(listen_once, "pending_camera_cmd", None)
            if camera_cmd:
                run_camera_command(camera_cmd, dry_run=args.dry_run)
                print("[LISTENER] camera run finished; reopening UART and resubscribing")
                time.sleep(1.0)
                continue

            if not should_continue:
                return 0

    except KeyboardInterrupt:
        print("\n[LISTENER] stopped by user")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
