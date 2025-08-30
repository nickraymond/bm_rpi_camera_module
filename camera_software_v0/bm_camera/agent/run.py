#!/usr/bin/env python3
import logging
from bm_camera.common.logging_config import setup_logging
from bm_camera.common.logging_setup import setup_logging

from bm_camera.common.config import load_config

import signal, sys, time, hashlib, os
from pathlib import Path

from bm_camera.agent.bus import open_bus, subscribe_many, loop
from bm_camera.agent.dispatcher import build_dispatch, init_handlers, cleanup_handlers

# --------- graceful shutdown ---------
_running = True
def _term(*_):
	global _running
	_running = False
signal.signal(signal.SIGTERM, _term)
signal.signal(signal.SIGINT, _term)

# --------- de-dupe config ---------
DEDUP_DEFAULT_WINDOW_S = 2.0
# mode:
#   - "by_payload": drop only exact repeat of same node/topic/payload
#   - "by_topic":   drop any repeat of same node/topic regardless of payload (ideal for triggers)
DEDUP_RULES = {
	"camera/capture/video": {"window": 8.0, "mode": "by_topic"},
	"camera/capture/image": {"window": 5.0, "mode": "by_topic"},
}

_recent = {}                # key -> (last_seen_monotonic, ttl)
_RECENT_SOFT_MAX = 4096     # prune threshold

# --------- utils ---------
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

def _payload_hash(data: bytes) -> bytes:
	return hashlib.blake2b(data, digest_size=8).digest() if data else b""

def _dedupe_key(node_id: int, topic_str: str, data: bytes, mode: str):
	if mode == "by_topic":
		return ("topic", node_id, topic_str)
	return ("payload", node_id, topic_str, _payload_hash(data))

def _rule_for(topic_str: str):
	return DEDUP_RULES.get(topic_str, {"window": DEDUP_DEFAULT_WINDOW_S, "mode": "by_payload"})

def _payload_to_str(data: bytes) -> str:
	if not data:
		return ""
	body = data[1:] if data and data[0] < 0x20 else data  # strip 1B BM type if present
	s = body.decode("utf-8", "ignore").strip()
	if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
		s = s[1:-1]
	return s

def _parse_secs(token: str) -> float:
	v = token.lower()
	if v.endswith("ms"):
		return float(v[:-2]) / 1000.0
	if v.endswith("s"):
		return float(v[:-1])
	return float(v)

def _dynamic_window(topic_str: str, data: bytes, base_window: float) -> float:
	# Expand the de-dupe window based on payload for certain topics.
	if topic_str == "camera/capture/video":
		s = _payload_to_str(data)
		dur = None
		if s and s not in ("1", "go", "trigger"):
			for tok in s.split(","):
				if "=" in tok:
					k, v = tok.split("=", 1)
					if k.strip().lower() == "dur":
						try:
							dur = _parse_secs(v.strip())
						except Exception:
							pass
		if dur is None:
			dur = 3.0  # default video duration in your handler
		return max(base_window, float(dur) + 5.0)  # safety margin after recording ends
	return base_window

def _prune_recent(now: float):
	if len(_recent) <= _RECENT_SOFT_MAX:
		return
	for k, (seen, ttl) in list(_recent.items()):
		if now - seen >= ttl:
			_recent.pop(k, None)

def _is_dup(node_id, topic_str, data: bytes) -> bool:
	now = time.monotonic()
	rule = _rule_for(topic_str)
	base_win = float(rule.get("window", DEDUP_DEFAULT_WINDOW_S))
	mode = rule.get("mode", "by_payload")

	win = _dynamic_window(topic_str, data, base_win)
	key = _dedupe_key(node_id, topic_str, data, mode)

	hit = key in _recent and (now - _recent[key][0]) < _recent[key][1]
	_recent[key] = (now, win)
	if hit:
		return True

	_prune_recent(now)
	return False

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
# def main():
# 	# 1) Load YAML (shared) and set up logging first
# 	# from bm_camera.common.config import load_config
# 	# from bm_camera.common.logging_config import setup_logging
# 	# import logging
# 
# 	cfg = load_config()                  # replaces _load_cfg()
# 	logger = setup_logging(cfg)          # enable console + rotating-file logs
# 
# 	# 2) Build handler context (stash cfg so handlers can read defaults/paths)
# 	ctx = init_handlers(cfg)
# 	ctx["cfg"] = cfg
# 
# 	# 3) Build dispatch table
# 	raw_dispatch = build_dispatch(cfg)
# 	dispatch = {_norm_topic(k): v for k, v in raw_dispatch.items()}
# 
# 	logger.info("[DISPATCH] topics=%s", list(dispatch.keys()))
# 
# 	# 4) Subscriber callback with de-dupe
# 	def cb(node_id, type_, version, topic_len, topic, data_len, data: bytes):
# 		topic_str = _norm_topic(topic)
# 
# 		# Drop duplicates BEFORE logging/handling
# 		if _is_dup(node_id, topic_str, data):
# 			return
# 
# 		logger.info("[PUB] node=%s type=%s ver=%s topic='%s' len=%s",
# 					hex(node_id), type_, version, topic_str, data_len)
# 
# 		handler = dispatch.get(topic_str)
# 		if handler:
# 			try:
# 				handler(node_id, topic_str, data, ctx)
# 			except Exception as e:
# 				logger.exception("[HANDLER][ERR] %r", e)
# 		else:
# 			logger.warning("[WARN] no handler for topic '%s' (known: %s)",
# 						   topic_str, list(dispatch.keys()))
# 
# 	# 5) Open bus and subscribe
# 	bm = open_bus(cfg.get("uart_device", "/dev/serial0"),
# 				  cfg.get("baudrate", 115200))
# 	ctx["bm"] = bm
# 	subscribe_many(bm, list(dispatch.keys()), cb)
# 
# 	try:
# 		logger.info("[RUN] bm-agent running…")
# 		loop(bm, lambda: not _running)
# 	finally:
# 		cleanup_handlers(ctx)
def main():
	cfg = _load_cfg()
	setup_logging(cfg)                     # <-- NEW: init logging early
	log = logging.getLogger("bm_camera.agent")
	
	ctx = init_handlers(cfg)
	
	raw_dispatch = build_dispatch(cfg)
	dispatch = {_norm_topic(k): v for k, v in raw_dispatch.items()}
	
	log.info("CONFIG using %s", DEFAULT_CFG_PATH)
	log.info("DISPATCH topics=%s", list(dispatch.keys()))
	
	def cb(node_id, type_, version, topic_len, topic, data_len, data: bytes):
		topic_str = _norm_topic(topic)
		if _is_dup(node_id, topic_str, data):
			return
	
		log.info("PUB node=%s type=%s ver=%s topic='%s' len=%s",
				hex(node_id), type_, version, topic_str, data_len)
	
		handler = dispatch.get(topic_str)
		if handler:
			try:
				handler(node_id, topic_str, data, ctx)
			except Exception as e:
				log.exception("HANDLER error: %r", e)
		else:
			log.warning("No handler for topic '%s' (known=%s)", topic_str, list(dispatch.keys()))
	
	bm = open_bus(cfg["uart_device"], cfg["baudrate"])
	ctx["bm"] = bm
	subscribe_many(bm, list(dispatch.keys()), cb)
	
	try:
		log.info("RUN bm-agent running…")
		loop(bm, lambda: not _running)
	finally:
		cleanup_handlers(ctx)

if __name__ == "__main__":
	sys.exit(main())
