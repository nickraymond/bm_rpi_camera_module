# # # #!/usr/bin/env python3
# # # import signal
# # # import sys
# # # 
# # # from bm_agent.config import load_config
# # # from bm_agent.bus import open_bus, subscribe_many, loop
# # # from bm_agent.dispatcher import build_dispatch, init_handlers, cleanup_handlers
# # # 
# # # # --------- graceful shutdown ---------
# # # _running = True
# # # def _term(*_):
# # # 	global _running
# # # 	_running = False
# # # 
# # # signal.signal(signal.SIGTERM, _term)
# # # signal.signal(signal.SIGINT, _term)
# # # 
# # # # --------- utilities ---------
# # # def _norm_topic(x):
# # # 	"""
# # # 	Normalize a topic to a clean str:
# # # 	  - bytes/bytearray  -> UTF-8 string
# # # 	  - stringified bytes like "b'foo/bar'" or 'b"foo/bar"' -> extract inner
# # # 	  - strip trailing NULs
# # # 	"""
# # # 	# Case 1: real bytes-like
# # # 	if isinstance(x, (bytes, bytearray)):
# # # 		try:
# # # 			s = x.decode("utf-8", "ignore")
# # # 		except Exception:
# # # 			s = str(x)
# # # 		return s.rstrip("\x00")
# # # 
# # # 	# Case 2: already a str (possibly "b'...'" or 'b"..."')
# # # 	s = str(x).strip().rstrip("\x00")
# # # 
# # # 	if (s.startswith("b'") and s.endswith("'")) or (s.startswith('b"') and s.endswith('"')):
# # # 		# Extract the inner content
# # # 		inner = s[2:-1]
# # # 		return inner
# # # 
# # # 	return s
# # # 
# # # # --------- main ---------
# # # def main():
# # # 	cfg = load_config()
# # # 	ctx = init_handlers(cfg)
# # # 
# # # 	# Build dispatch and normalize keys so bytes vs str never mismatches
# # # 	raw_dispatch = build_dispatch(cfg)
# # # 	dispatch = { _norm_topic(k): v for k, v in raw_dispatch.items() }
# # # 
# # # 	print(f"[DISPATCH] topics={list(dispatch.keys())}")
# # # 
# # # 	def cb(node_id, type_, version, topic_len, topic, data_len, data: bytes):
# # # 		print()  # newline to break heartbeat dots
# # # 		topic_str = _norm_topic(topic)
# # # 		print(f"[PUB] node={hex(node_id)} type={type_} ver={version} topic='{topic_str}' len={data_len}")
# # # 		handler = dispatch.get(topic_str)
# # # 		if handler:
# # # 			handler(node_id, topic_str, data, ctx)
# # # 		else:
# # # 			# Helpful hint once so it's easy to see what arrived vs what we're mapping
# # # 			print(f"[WARN] no handler for topic '{topic_str}' (known: {list(dispatch.keys())})")
# # # 
# # # 	bm = open_bus(cfg["uart_device"], cfg["baudrate"])
# # # 	subscribe_many(bm, list(dispatch.keys()), cb)
# # # 
# # # 	try:
# # # 		print("[RUN] bm-agent running…")
# # # 		loop(bm, lambda: not _running)
# # # 	finally:
# # # 		cleanup_handlers(ctx)
# # # 
# # # if __name__ == "__main__":
# # # 	sys.exit(main())
# # #!/usr/bin/env python3
# # import signal
# # import sys
# # import time
# # import hashlib
# # 
# # from bm_agent.config import load_config
# # from bm_agent.bus import open_bus, subscribe_many, loop
# # from bm_agent.dispatcher import build_dispatch, init_handlers, cleanup_handlers
# # 
# # # --------- graceful shutdown ---------
# # _running = True
# # def _term(*_):
# # 	global _running
# # 	_running = False
# # 
# # signal.signal(signal.SIGTERM, _term)
# # signal.signal(signal.SIGINT, _term)
# # 
# # # --------- dedupe (drop retransmits within a short window) ---------
# # DEDUP_WINDOW_S = 1.0
# # _recent = {}  # (node_id, topic_str, hash(payload)) -> last_seen_monotonic
# # 
# # def _dedupe_key(node_id, topic_str, data):
# # 	h = hashlib.blake2b(data, digest_size=8).digest() if data else b""
# # 	return (node_id, topic_str, h)
# # 
# # def _is_dup(node_id, topic_str, data):
# # 	now = time.monotonic()
# # 	key = _dedupe_key(node_id, topic_str, data)
# # 	last = _recent.get(key)
# # 	if last is not None and (now - last) < DEDUP_WINDOW_S:
# # 		return True
# # 	_recent[key] = now
# # 	# light pruning
# # 	if len(_recent) > 1024:
# # 		cutoff = now - DEDUP_WINDOW_S
# # 		for k, t in list(_recent.items()):
# # 			if t < cutoff:
# # 				_recent.pop(k, None)
# # 	return False
# # 
# # # --------- utilities ---------
# # def _norm_topic(x):
# # 	"""
# # 	Normalize a topic to a clean str:
# # 	  - bytes/bytearray  -> UTF-8 string
# # 	  - stringified bytes like "b'foo/bar'" or 'b"foo/bar"' -> extract inner
# # 	  - strip trailing NULs
# # 	"""
# # 	if isinstance(x, (bytes, bytearray)):
# # 		try:
# # 			s = x.decode("utf-8", "ignore")
# # 		except Exception:
# # 			s = str(x)
# # 		return s.rstrip("\x00")
# # 
# # 	s = str(x).strip().rstrip("\x00")
# # 	if (s.startswith("b'") and s.endswith("'")) or (s.startswith('b"') and s.endswith('"')):
# # 		return s[2:-1]
# # 	return s
# # 
# # # --------- main ---------
# # def main():
# # 	cfg = load_config()
# # 	ctx = init_handlers(cfg)
# # 
# # 	raw_dispatch = build_dispatch(cfg)
# # 	dispatch = { _norm_topic(k): v for k, v in raw_dispatch.items() }
# # 
# # 	print(f"[DISPATCH] topics={list(dispatch.keys())}")
# # 
# # 	def cb(node_id, type_, version, topic_len, topic, data_len, data: bytes):
# # 		print()  # newline to break heartbeat dots
# # 		topic_str = _norm_topic(topic)
# # 		print(f"[PUB] node={hex(node_id)} type={type_} ver={version} topic='{topic_str}' len={data_len}")
# # 
# # 		# drop duplicates (same node/topic/payload within DEDUP_WINDOW_S)
# # 		if _is_dup(node_id, topic_str, data):
# # 			# print("(dup dropped)")  # uncomment if you want to see drops
# # 			return
# # 
# # 		handler = dispatch.get(topic_str)
# # 		if handler:
# # 			try:
# # 				handler(node_id, topic_str, data, ctx)
# # 			except Exception as e:
# # 				print(f"[HANDLER][ERR] {e!r}")
# # 		else:
# # 			print(f"[WARN] no handler for topic '{topic_str}' (known: {list(dispatch.keys())})")
# # 
# # 	bm = open_bus(cfg["uart_device"], cfg["baudrate"])
# # 	subscribe_many(bm, list(dispatch.keys()), cb)
# # 
# # 	try:
# # 		print("[RUN] bm-agent running…")
# # 		loop(bm, lambda: not _running)
# # 	finally:
# # 		cleanup_handlers(ctx)
# # 
# # if __name__ == "__main__":
# # 	sys.exit(main())
# #!/usr/bin/env python3
# import signal, sys, time, hashlib, os
# from pathlib import Path
# 
# from bm_agent.config import load_config
# from bm_agent.bus import open_bus, subscribe_many, loop
# from bm_agent.dispatcher import build_dispatch, init_handlers, cleanup_handlers
# 
# # --------- graceful shutdown ---------
# _running = True
# def _term(*_):
# 	global _running
# 	_running = False
# signal.signal(signal.SIGTERM, _term)
# signal.signal(signal.SIGINT, _term)
# 
# # --------- dedupe ---------
# DEDUP_WINDOW_S = 1.0
# _recent = {}
# def _dedupe_key(node_id, topic_str, data):
# 	h = hashlib.blake2b(data, digest_size=8).digest() if data else b""
# 	return (node_id, topic_str, h)
# def _is_dup(node_id, topic_str, data):
# 	now = time.monotonic()
# 	key = _dedupe_key(node_id, topic_str, data)
# 	last = _recent.get(key)
# 	if last is not None and (now - last) < DEDUP_WINDOW_S:
# 		return True
# 	_recent[key] = now
# 	if len(_recent) > 1024:
# 		cutoff = now - DEDUP_WINDOW_S
# 		for k, t in list(_recent.items()):
# 			if t < cutoff:
# 				_recent.pop(k, None)
# 	return False
# 
# # --------- topic normalize ---------
# def _norm_topic(x):
# 	if isinstance(x, (bytes, bytearray)):
# 		try:
# 			s = x.decode("utf-8", "ignore")
# 		except Exception:
# 			s = str(x)
# 		return s.rstrip("\x00")
# 	s = str(x).strip().rstrip("\x00")
# 	if (s.startswith("b'") and s.endswith("'")) or (s.startswith('b"') and s.endswith('"')):
# 		return s[2:-1]
# 	return s
# 
# # --------- load config anchored to this file ---------
# HERE = Path(__file__).resolve().parent
# DEFAULT_CFG_PATH = HERE / "config.yaml"
# 
# def _load_cfg():
# 	# 1) Env override if provided
# 	env_path = os.environ.get("BM_AGENT_CONFIG")
# 	if env_path:
# 		return load_config(env_path)
# 	# 2) Try explicit path form of load_config
# 	try:
# 		return load_config(str(DEFAULT_CFG_PATH))
# 	except TypeError:
# 		# 3) Fallback: temporarily chdir so legacy load_config() finds ./config.yaml
# 		prev = os.getcwd()
# 		try:
# 			os.chdir(str(HERE))
# 			return load_config()
# 		finally:
# 			os.chdir(prev)
# 
# # --------- main ---------
# def main():
# 	cfg = _load_cfg()
# 	ctx = init_handlers(cfg)
# 
# 	raw_dispatch = build_dispatch(cfg)
# 	dispatch = { _norm_topic(k): v for k, v in raw_dispatch.items() }
# 
# 	print(f"[CONFIG] using {DEFAULT_CFG_PATH}")
# 	print(f"[DISPATCH] topics={list(dispatch.keys())}")
# 
# 	def cb(node_id, type_, version, topic_len, topic, data_len, data: bytes):
# 		print()
# 		topic_str = _norm_topic(topic)
# 		print(f"[PUB] node={hex(node_id)} type={type_} ver={version} topic='{topic_str}' len={data_len}")
# 		if _is_dup(node_id, topic_str, data):
# 			return
# 		handler = dispatch.get(topic_str)
# 		if handler:
# 			try:
# 				handler(node_id, topic_str, data, ctx)
# 			except Exception as e:
# 				print(f"[HANDLER][ERR] {e!r}")
# 		else:
# 			print(f"[WARN] no handler for topic '{topic_str}' (known: {list(dispatch.keys())})")
# 
# 	bm = open_bus(cfg["uart_device"], cfg["baudrate"])
# 	subscribe_many(bm, list(dispatch.keys()), cb)
# 
# 	try:
# 		print("[RUN] bm-agent running…")
# 		loop(bm, lambda: not _running)
# 	finally:
# 		cleanup_handlers(ctx)
# 
# if __name__ == "__main__":
# 	sys.exit(main())
#!/usr/bin/env python3
import signal, sys, time, hashlib, os
from pathlib import Path

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

# --------- dedupe (drop retransmits within a short window) ---------
DEDUP_WINDOW_S = 2.0
_recent = {}  # (node_id, topic_str, hash(payload)) -> last_seen_monotonic

def _dedupe_key(node_id, topic_str, data):
	h = hashlib.blake2b(data, digest_size=8).digest() if data else b""
	return (node_id, topic_str, h)

def _is_dup(node_id, topic_str, data):
	now = time.monotonic()
	key = _dedupe_key(node_id, topic_str, data)
	last = _recent.get(key)
	if last is not None and (now - last) < DEDUP_WINDOW_S:
		return True
	_recent[key] = now
	# light pruning
	if len(_recent) > 1024:
		cutoff = now - DEDUP_WINDOW_S
		for k, t in list(_recent.items()):
			if t < cutoff:
				_recent.pop(k, None)
	return False

# --------- topic normalize ---------
def _norm_topic(x):
	if isinstance(x, (bytes, bytearray)):
		try:
			s = x.decode("utf-8", "ignore")
		except Exception:
			s = str(x)
		return s.rstrip("\x00")
	s = str(x).strip().rstrip("\x00")
	if (s.startswith("b'") and s.endswith("'")) or (s.startswith('b"') and s.endswith('"')):
		return s[2:-1]
	return s

# --------- load config anchored to this file ---------
HERE = Path(__file__).resolve().parent
DEFAULT_CFG_PATH = HERE / "config.yaml"

def _load_cfg():
	env_path = os.environ.get("BM_AGENT_CONFIG")
	if env_path:
		return load_config(env_path)
	try:
		return load_config(str(DEFAULT_CFG_PATH))
	except TypeError:
		prev = os.getcwd()
		try:
			os.chdir(str(HERE))
			return load_config()
		finally:
			os.chdir(prev)

# --------- main ---------
def main():
	cfg = _load_cfg()
	ctx = init_handlers(cfg)

	raw_dispatch = build_dispatch(cfg)
	dispatch = { _norm_topic(k): v for k, v in raw_dispatch.items() }

	print(f"[CONFIG] using {DEFAULT_CFG_PATH}")
	print(f"[DISPATCH] topics={list(dispatch.keys())}")

	def cb(node_id, type_, version, topic_len, topic, data_len, data: bytes):
		# Drop duplicates BEFORE we print anything
		topic_str = _norm_topic(topic)
		if _is_dup(node_id, topic_str, data):
			return

		# Only log non-duplicates
		print()
		print(f"[PUB] node={hex(node_id)} type={type_} ver={version} topic='{topic_str}' len={data_len}")

		handler = dispatch.get(topic_str)
		if handler:
			try:
				handler(node_id, topic_str, data, ctx)
			except Exception as e:
				print(f"[HANDLER][ERR] {e!r}")
		else:
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
