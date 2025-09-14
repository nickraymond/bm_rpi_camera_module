#!/usr/bin/env python3
import logging
import signal, sys, time, hashlib, os
from pathlib import Path

from bm_camera.common.logging_config import setup_logging
from bm_camera.common.config import load_config
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
DEDUP_DEFAULT_WINDOW_S = 0.10
# mode:
#   - "by_payload": drop only exact repeat of same node/topic/payload
#   - "by_topic":   drop any repeat of same node/topic regardless of payload (ideal for triggers)
DEDUP_RULES = {
	"camera/capture/video": {"window": 0.10,  "mode": "by_topic"},
	"camera/capture/image": {"window": 0.10, "mode": "by_topic"},  # give TX time to finish
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

	prev = _recent.get(key)
	hit = (prev is not None) and ((now - prev[0]) < prev[1])

	# Always update the watermark so a stream of repeats stays suppressed
	_recent[key] = (now, win)

	if hit:
		lg = logging.getLogger("AGENT")
		delta = now - prev[0]
		if topic_str == "camera/capture/image":
			lg.warning("DEDUP drop topic='%s' window=%.1fs Δ=%.2fs payload='%s'",
					   topic_str, win, delta, _payload_to_str(data))
		else:
			lg.warning("DEDUP drop topic='%s' window=%.1fs", topic_str, win)
		return True

	_prune_recent(now)
	return False

# --------- load config (no-arg loader) ---------
def _load_cfg():
	return load_config()

def main():
	cfg = _load_cfg()

	# Init logging early using YAML settings
	setup_logging(cfg)
	log = logging.getLogger("AGENT")

	ctx = init_handlers(cfg)

	raw_dispatch = build_dispatch(cfg)
	# ensure unique topics before subscribe
	topics = sorted(set(_norm_topic(k) for k in raw_dispatch.keys()))
	dispatch = {t: raw_dispatch[t] for t in topics if t in raw_dispatch}

	log.info("CONFIG loaded")
	log.info("DISPATCH topics=%s", topics)

	def cb(node_id, type_, version, topic_len, topic, data_len, data: bytes):
		topic_str = _norm_topic(topic)

		# Drop duplicates BEFORE logging/handling
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
	subscribe_many(bm, topics, cb)

	try:
		log.info("RUN bm-agent running…")
		loop(bm, lambda: not _running)
	finally:
		cleanup_handlers(ctx)

if __name__ == "__main__":
	sys.exit(main())
