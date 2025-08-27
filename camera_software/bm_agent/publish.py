# bm_agent/publish.py
# Bench & helper to publish to a BM topic from the Pi.

import argparse
import json
from pathlib import Path
import sys

# Import BristlemouthSerial from your project root
PROJECT = Path.home() / "bm_camera" / "camera_software"
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))
from bm_serial import BristlemouthSerial  # noqa

TYPE_TEXT = 0x00
TYPE_JSON = 0x03  # keep for bench publishing JSON

def _pub_header(bm: BristlemouthSerial, header_type=None, header_version=None) -> bytes:
    """
    Start with bm.get_pub_header() (which in your tree sets type/ver=1/1),
    and optionally override the trailing type/version bytes.
    """
    hdr = bytearray(bm.get_pub_header())
    if header_type is not None:
        hdr[-2] = int(header_type) & 0xFF
    if header_version is not None:
        hdr[-1] = int(header_version) & 0xFF
    return bytes(hdr)

def bristlemouth_pub(bm: BristlemouthSerial,
                     topic: str,
                     payload_bytes: bytes,
                     payload_type: int = TYPE_TEXT,
                     header_type=None,
                     header_version=None) -> None:
    """Low-level publisher used by helpers below."""
    hdr = _pub_header(bm, header_type, header_version)
    t = topic.encode("utf-8")
    # Wire format: [hdr][topic_len][topic][payload_type][payload]
    frame = bytearray(hdr + len(t).to_bytes(2, "little") + t + bytes([payload_type]) + payload_bytes)
    cobs = bm.finalize_packet(frame)
    bm.lock_uart_and_write_bytes(cobs)

def pub_text(bm: BristlemouthSerial, topic: str, text: str, version=None, **_ignore) -> None:
    """
    Publish plain text (type byte 0x00).
    Accepts extra kwargs (like version=0) so callers don't break.
    If version is provided, we set the publish header's version field to match.
    """
    payload = text.encode("utf-8")
    bristlemouth_pub(bm, topic, payload, TYPE_TEXT, header_version=version)

def pub_json(bm: BristlemouthSerial, topic: str, obj, version=None, **_ignore) -> None:
    """
    Publish JSON (type byte 0x03).
    """
    payload = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    bristlemouth_pub(bm, topic, payload, TYPE_JSON, header_version=version)

# ---- CLI bench tool ----
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topic", help="BM topic, e.g. camera/status")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", help="Plain text payload")
    g.add_argument("--json", help='JSON string payload, e.g. \'{"k":"v"}\'')
    ap.add_argument("--ver", "--version", type=int, default=None, help="Override header version (e.g. 0)")
    args = ap.parse_args()

    bm = BristlemouthSerial()
    if args.text is not None:
        pub_text(bm, args.topic, args.text, version=args.ver)
        print(f"[PUB/TEXT] {args.topic} {args.text} ver={args.ver if args.ver is not None else 'hdr-default'}")
    else:
        pub_json(bm, args.topic, json.loads(args.json), version=args.ver)
        print(f"[PUB/JSON] {args.topic} {args.json} ver={args.ver if args.ver is not None else 'hdr-default'}")

if __name__ == "__main__":
    main()
