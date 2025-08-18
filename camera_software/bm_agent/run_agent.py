#!/usr/bin/env python3
import signal
import sys

from bm_agent.config import load_config
from bm_agent.bus import open_bus, subscribe_many, loop
from bm_agent.dispatcher import build_dispatch, init_handlers, cleanup_handlers

# --------- graceful shutdown ---------
_running = True
def _term(*_):
	global _running
	_running = False

signal.signal(signal.SIGTERM, _term)
signal.signal(signal.SIGINT, _term)

# --------- utilities ---------
def _norm_topic(x):
	"""
	Normalize a topic to a clean str:
	  - bytes/bytearray  -> UTF-8 string
	  - stringified bytes like "b'foo/bar'" or 'b"foo/bar"' -> extract inner
	  - strip trailing NULs
	"""
	# Case 1: real bytes-like
	if isinstance(x, (bytes, bytearray)):
		try:
			s = x.decode("utf-8", "ignore")
		except Exception:
			s = str(x)
		return s.rstrip("\x00")

	# Case 2: already a str (possibly "b'...'" or 'b"..."')
	s = str(x).strip().rstrip("\x00")

	if (s.startswith("b'") and s.endswith("'")) or (s.startswith('b"') and s.endswith('"')):
		# Extract the inner content
		inner = s[2:-1]
		return inner

	return s

# --------- main ---------
def main():
	cfg = load_config()
	ctx = init_handlers(cfg)

	# Build dispatch and normalize keys so bytes vs str never mismatches
	raw_dispatch = build_dispatch(cfg)
	dispatch = { _norm_topic(k): v for k, v in raw_dispatch.items() }

	print(f"[DISPATCH] topics={list(dispatch.keys())}")

	def cb(node_id, type_, version, topic_len, topic, data_len, data: bytes):
		print()  # newline to break heartbeat dots
		topic_str = _norm_topic(topic)
		print(f"[PUB] node={hex(node_id)} type={type_} ver={version} topic='{topic_str}' len={data_len}")
		handler = dispatch.get(topic_str)
		if handler:
			handler(node_id, topic_str, data, ctx)
		else:
			# Helpful hint once so it's easy to see what arrived vs what we're mapping
			print(f"[WARN] no handler for topic '{topic_str}' (known: {list(dispatch.keys())})")

	bm = open_bus(cfg["uart_device"], cfg["baudrate"])
	subscribe_many(bm, list(dispatch.keys()), cb)

	try:
		print("[RUN] bm-agent running…")
		loop(bm, lambda: not _running)
	finally:
		cleanup_handlers(ctx)

if __name__ == "__main__":
	sys.exit(main())
