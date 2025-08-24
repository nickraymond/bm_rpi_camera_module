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

# --------- de-dupe config ---------
DEDUP_DEFAULT_WINDOW_S = 2.0

# Per-topic rules: window + mode
# mode:
#   - "by_payload": drop only exact repeat of same node/topic/payload
#   - "by_topic":   drop any repeat of same node/topic regardless of payload (ideal for triggers)
DEDUP_RULES = {
	"camera/capture/video": {"window": 8.0, "mode": "by_topic"},  # already working well
	"camera/capture/image": {"window": 5.0, "mode": "by_topic"},  # NEW: tiny still-image dedupe
	# leave 'spotter/utc-time' with default (no dedupe) so the RTC flows
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
	# plain number -> seconds
	return float(v)

def _dynamic_window(topic_str: str, data: bytes, base_window: float) -> float:
	"""
	Expand the de-dupe window based on payload for certain topics.
	- video: window >= duration + 5s (so a single command campaign makes exactly one clip)
	- image: could also consider burst*interval, but base window is usually enough
	"""
	if topic_str == "camera/capture/video":
		s = _payload_to_str(data)
		# parse CSV key=val; look for dur=...
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
def main():
	cfg = _load_cfg()
	ctx = init_handlers(cfg)

	raw_dispatch = build_dispatch(cfg)
	dispatch = {_norm_topic(k): v for k, v in raw_dispatch.items()}

	print(f"[CONFIG] using {DEFAULT_CFG_PATH}")
	print(f"[DISPATCH] topics={list(dispatch.keys())}")

	def cb(node_id, type_, version, topic_len, topic, data_len, data: bytes):
		topic_str = _norm_topic(topic)

		# Drop duplicates BEFORE logging/handling
		if _is_dup(node_id, topic_str, data):
			return

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
