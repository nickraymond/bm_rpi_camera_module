
# filename: publish.py
# description: Bench tool to publish JSON to a BM topic from the Pi.

import argparse
import json
from pathlib import Path
import sys

# Import BristlemouthSerial from your project
PROJECT = Path.home() / "bm_camera" / "camera_software"
sys.path.append(str(PROJECT))
from bm_serial import BristlemouthSerial

# def bristlemouth_pub(bm: BristlemouthSerial, topic: str, payload: bytes):
#     hdr = bm.get_pub_header()
#     t = topic.encode("utf-8")
#     p = payload
#     packet = bytearray(hdr + len(t).to_bytes(2, "little") + t + len(p).to_bytes(2, "little") + p)
#     cobs = bm.finalize_packet(packet)
#     bm.lock_uart_and_write_bytes(cobs)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topic", help="BM topic, e.g. camera/still/capture")
    ap.add_argument("--json", default="{}", help="JSON payload string")
    args = ap.parse_args()

    bm = BristlemouthSerial()
    # payload = args.json.encode("utf-8")
    # bristlemouth_pub(bm, args.topic, payload)
    
    payload = args.json.encode("utf-8")
    bristlemouth_pub(bm, args.topic, payload, TYPE_JSON)
    
    print(f"[PUB] {args.topic} {args.json}")
    
# ...imports...
TYPE_JSON = 0x03  # set to match your bm CLI; change if your CLI uses a different code

def bristlemouth_pub(bm: BristlemouthSerial, topic: str, payload_bytes: bytes, type_byte: int = TYPE_JSON):
    hdr = bm.get_pub_header()
    t = topic.encode("utf-8")
    # NOTE: no payload length here; just the single type byte, then payload
    frame = bytearray(hdr + len(t).to_bytes(2, "little") + t + bytes([type_byte]) + payload_bytes)
    cobs = bm.finalize_packet(frame)
    bm.lock_uart_and_write_bytes(cobs)

if __name__ == "__main__":
    main()
