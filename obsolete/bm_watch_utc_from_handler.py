#!/usr/bin/env python3
"""
Smoke test: listen for 'spotter/utc-time', decode using your handler's logic,
and print the parsed timestamp. Does NOT adjust the system clock.

Usage:
  # Stop anything else that owns /dev/serial0
  pkill -f "bm_camera.agent" || true

  python bm_watch_utc_from_handler.py --uart /dev/serial0 --baud 115200
  # Optional: send a single local test frame (to prove wiring)
  python bm_watch_utc_from_handler.py --self-test
"""

import argparse, binascii, time, struct
from datetime import datetime, timezone, timedelta

from bm_camera.io.bm_serial import BristlemouthSerial
# Reuse your decode function from the handler module
from bm_camera.agent.handlers import clock as clock_mod

def iso_utc():
	return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def norm_topic(t) -> str:
	if isinstance(t, (bytes, bytearray)):
		s = t.decode("utf-8", "ignore").rstrip("\x00")
	else:
		s = str(t).rstrip("\x00")
	if (s.startswith("b'") and s.endswith("'")) or (s.startswith('b"') and s.endswith('"')):
		s = s[2:-1]
	return s.strip()

def parse_with_handler(payload: bytes):
	"""Use your handler's strict decoder (LE uint64 microseconds since epoch)."""
	try:
		return clock_mod._decode_epoch_dt_from_payload(payload)
	except Exception:
		# Fallback: try both endian just in case
		if len(payload) >= 8:
			for endian in ("<", ">"):
				try:
					ts_us, = struct.unpack(f"{endian}Q", payload[:8])
					if 946684800_000000 <= ts_us <= 4102444800_000000:  # 2000..2100
						return datetime.fromtimestamp(ts_us / 1e6, tz=timezone.utc)
				except Exception:
					pass
		return None

def self_test_publish(bm):
	"""Publish a single correct spotter/utc-time frame (type=1, ver=1) with now()"""
	topic = "spotter/utc-time"
	now_us = int((datetime.now(timezone.utc) - datetime(1970,1,1,tzinfo=timezone.utc)).total_seconds() * 1_000_000)
	payload = struct.pack("<Q", now_us)
	bm.bristlemouth_publish(topic, payload, 1, header_version=1)
	print(f"{iso_utc()} [UTCWATCH] [INFO] self-test published one frame to '{topic}'")

def on_rx(args_tuple):
	node_id, type_, version, topic_len, topic, data_len, data = args_tuple
	top = norm_topic(topic)
	hex32 = binascii.hexlify((data or b'')[:32]).decode("ascii")
	dt = parse_with_handler(data or b"")
	tiso = dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ") if dt else "unparsed"

	print(f"{iso_utc()} [UTCWATCH] [INFO] RX node={hex(node_id)} type={type_} ver={version} "
		  f"topic='{top}' len={data_len}")
	print(f"{iso_utc()} [UTCWATCH] [DEBUG] payload[:32]=0x{hex32}")
	print(f"{iso_utc()} [UTCWATCH] [INFO] parsed_ts={tiso}")

def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--uart", default="/dev/serial0")
	ap.add_argument("--baud", type=int, default=115200)
	ap.add_argument("--topic", default="spotter/utc-time")
	ap.add_argument("--drain-seconds", type=float, default=0.5)
	ap.add_argument("--self-test", action="store_true", help="Publish one local time frame")
	args = ap.parse_args()

	bm = BristlemouthSerial(port=args.uart, baudrate=args.baud, timeout=0.5)

	# Drain any backlog before subscribing
	if args.drain_seconds > 0:
		end = time.time() + args.drain_seconds
		while time.time() < end:
			bm.bristlemouth_process(0.05)
			time.sleep(0.01)

	print(f"{iso_utc()} [UTCWATCH] [INFO] open {args.uart} @{args.baud}")
	bm.bristlemouth_sub(args.topic, lambda *cb_args: on_rx(cb_args))
	print(f"{iso_utc()} [UTCWATCH] [INFO] subscribed '{args.topic}'")

	if args.self_test:
		self_test_publish(bm)

	last_hb = 0.0
	try:
		while True:
			bm.bristlemouth_process(0.1)
			now = time.monotonic()
			if now - last_hb >= 5.0:
				print(f"{iso_utc()} [UTCWATCH] [DEBUG] HB")
				last_hb = now
			time.sleep(0.02)
	finally:
		try:
			bm.uart.close()
		except Exception:
			pass
		print(f"{iso_utc()} [UTCWATCH] [INFO] closed")

if __name__ == "__main__":
	main()
