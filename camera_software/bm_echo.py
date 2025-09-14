#!/usr/bin/env python3
"""
Minimal Bristlemouth RX sniffer for debugging duplicates.

Usage (stop your agent first so the UART is free):
  python tools/bm_echo.py --uart /dev/serial0 --baud 115200 --topic test/pi

From the Bridge:
  bm pub test/pi "hello"

If you send exactly one publish from the Bridge and see >1 RX lines here,
the duplicate is upstream of your Python handlers.
"""

import argparse
import binascii
import hashlib
import time
from datetime import datetime, timezone

from bm_camera.io.bm_serial import BristlemouthSerial

def iso_utc() -> str:
	return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def norm_topic(t) -> str:
	if isinstance(t, (bytes, bytearray)):
		s = t.decode("utf-8", "ignore").rstrip("\x00")
	else:
		s = str(t).rstrip("\x00")
	if (s.startswith("b'") and s.endswith("'")) or (s.startswith('b"') and s.endswith('"')):
		s = s[2:-1]
	return s.strip()


def payload_digest(b: bytes) -> str:
	if not b:
		return "∅"
	h = hashlib.blake2b(b, digest_size=8).hexdigest()
	return h


def main():
	ap = argparse.ArgumentParser(description="Bristlemouth echo/sniffer")
	ap.add_argument("--uart", default="/dev/serial0")
	ap.add_argument("--baud", type=int, default=115200)
	ap.add_argument("--topic", default="test/pi", help="Topic to subscribe to")
	ap.add_argument("--drain-seconds", type=float, default=0.0,
					help="Optional: process the bus for N seconds before subscribing (clears any backlog).")
	ap.add_argument("--flush-after", action="store_true",
					help="Optional: after each RX, reset UART input/output buffers (diagnostic only).")
	args = ap.parse_args()

	bm = BristlemouthSerial(port=args.uart, baudrate=args.baud, timeout=0.5)

	# Best-effort clean start
	uart = getattr(bm, "uart", None)
	if uart:
		try:
			uart.reset_input_buffer()
			uart.reset_output_buffer()
		except Exception:
			pass

	print(f"{iso_utc()} [ECHO] [INFO] open {args.uart} @{args.baud}")

	# Optional: drain any pending frames before we subscribe (to avoid attributing backlog as duplicates)
	if args.drain_seconds > 0:
		t_end = time.time() + args.drain_seconds
		while time.time() < t_end:
			bm.bristlemouth_process(0.05)
			time.sleep(0.01)
		print(f"{iso_utc()} [ECHO] [INFO] drained {args.drain_seconds:.2f}s pre-subscribe")

	# Subscribe after drain
	topic = str(args.topic)
	bm.bristlemouth_sub(topic, lambda *cb_args: on_rx(cb_args, args, bm))
	print(f"{iso_utc()} [ECHO] [INFO] subscribed '{topic}'")

	# Pump loop
	try:
		last_hb = 0.0
		while True:
			bm.bristlemouth_process(0.1)
			now = time.monotonic()
			if now - last_hb >= 5.0:
				print(f"{iso_utc()} [ECHO] [DEBUG] HB")
				last_hb = now
			time.sleep(0.02)
	finally:
		try:
			bm.uart.close()
		except Exception:
			pass
		print(f"{iso_utc()} [ECHO] [INFO] closed")


# Callback signature from BristlemouthSerial:
#   (node_id, type_, version, topic_len, topic, data_len, data)
_rx_count = 0
_last_seen = None  # (topic_str, blake8_hex, t_monotonic)


def on_rx(args_tuple, cli_args, bm):
	global _rx_count, _last_seen
	node_id, type_, version, topic_len, topic, data_len, data = args_tuple

	tnow = time.monotonic()
	tiso = iso_utc()
	top = norm_topic(topic)
	h   = payload_digest(data)
	snip = (data or b"")[:32]
	snip_hex = binascii.hexlify(snip).decode("ascii")

	_rx_count += 1
	# Duplicate hint (no suppression—just annotate)
	dup_note = ""
	if _last_seen is not None:
		last_top, last_h, last_t = _last_seen
		if (last_top == top) and (last_h == h):
			dup_note = f" (DUP +{(tnow - last_t)*1000:.1f}ms)"
	_last_seen = (top, h, tnow)

	print(f"{tiso} [ECHO] [INFO] RX #{_rx_count} "
		  f"node={hex(node_id)} type={type_} ver={version} topic='{top}' "
		  f"len={data_len} hash={h}{dup_note}")
	print(f"{tiso} [ECHO] [DEBUG] payload[0:32]=0x{snip_hex}")

	if cli_args.flush_after:
		uart = getattr(bm, "uart", None)
		if uart:
			try:
				uart.reset_input_buffer()
				uart.reset_output_buffer()
				print(f"{tiso} [ECHO] [DEBUG] uart flushed after RX")
			except Exception:
				print(f"{tiso} [ECHO] [WARN] uart flush failed")


if __name__ == "__main__":
	main()
