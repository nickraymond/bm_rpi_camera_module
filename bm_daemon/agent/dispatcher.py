# # filename: dispatcher.py
# 
# from .handlers import rtc, clock
# from .handlers import test_pi                      # if you’re using test/pi
# 
# def build_dispatch(cfg):
# 	topics = cfg.get("topics", {})
# 	table = {}
# 
# 	# RTC (optionally chained with clock)
# 	rtc_topic = topics.get("rtc")
# 	if rtc_topic:
# 		if cfg.get("clock", {}).get("enabled", False):
# 			def _rtc_and_clock(n, t, d, c):
# 				rtc.handle(n, t, d, c)
# 				clock.handle(n, t, d, c)
# 			table[rtc_topic] = _rtc_and_clock
# 		else:
# 			table[rtc_topic] = lambda n, t, d, c: rtc.handle(n, t, d, c)
# 
# 	# test/pi (optional)
# 	test_topic = topics.get("test_pi")
# 	if test_topic:
# 		table[test_topic] = lambda n, t, d, c: test_pi.handle(n, t, d, c)
# 
# 	# NEW: camera capture topics from your YAML
# 	img_topic = topics.get("camera_capture_image")     # camera/capture/image
# 	if img_topic:
# 
# 	vid_topic = topics.get("camera_capture_video")     # camera/capture/video
# 	if vid_topic:
# 
# 	# return only valid keys
# 	return {k: v for k, v in table.items() if k}
# 
# def init_handlers(cfg):
# 	ctx = {"cfg": cfg}
# 	if cfg.get("clock", {}).get("enabled", False):
# 		clock.init(ctx)
# 	# init your handlers (no-op init is fine)
# 	return ctx
# 
# def cleanup_handlers(ctx):
# 	if ctx.get("cfg", {}).get("clock", {}).get("enabled", False):
# 		clock.cleanup(ctx)

# 
# from typing import Callable, Dict, Iterable, Any, Optional, Optional
# 
# # Core dispatch table builder. Keep it empty/minimal; plugins are merged in run.py.
# def build_dispatch(cfg: dict) -> Dict[str, Callable[[str, str, bytes, dict], None]]:
# 	dispatch: Dict[str, Callable[[str, str, bytes, dict], None]] = {}
# 	# If you have core (non-plugin) handlers, add them here, e.g.:
# 	# dispatch["system/hello"] = hello_handler
# 	return dispatch
# 
# # Lifecycle hooks for handlers (no-op safe defaults).
# def init_handlers(handlers: Optional[Iterable[Any]] = None) -> None:
# 	if not handlers:
# 		return
# 	for h in handlers:
# 		init = getattr(h, "init", None)
# 		if callable(init):
# 			init()
# 
# def cleanup_handlers(handlers: Optional[Iterable[Any]] = None) -> None:
# 	if not handlers:
# 		return
# 	for h in handlers:
# 		fini = getattr(h, "cleanup", None)
# 		if callable(fini):
# 			fini()

# bm_daemon/agent/dispatcher.py
from typing import Callable, Dict, Iterable, Any, Optional
import logging

logger = logging.getLogger("DISPATCH")

# Return type: topic -> handler(node_id, topic_str, data_bytes, ctx_dict)
Dispatch = Dict[str, Callable[[int, str, bytes, dict], None]]

def _load_core_rtc_handler() -> Optional[Callable[[int, str, bytes, dict], None]]:
	"""
	Try to import a core RTC/clock handler from the daemon.
	Expected signature: handle(node_id, topic: str, data: bytes, ctx: dict) -> None
	"""
	# Prefer 'clock.py', but allow 'rtc.py' as a fallback.
	for modname in ("bm_daemon.agent.handlers.clock", "bm_daemon.agent.handlers.rtc"):
		try:
			mod = __import__(modname, fromlist=["*"])
		except Exception:
			continue
		# Common function names we might find
		for attr in ("handle", "on_message", "on_rtc"):
			fn = getattr(mod, attr, None)
			if callable(fn):
				logger.info("Core RTC handler: %s.%s", modname, attr)
				return fn
	logger.warning("No core RTC handler found (expected bm_daemon.agent.handlers.clock or ...rtc)")
	return None

def build_dispatch(cfg: dict) -> Dispatch:
	"""
	Build the core dispatch table (RTC, status, etc.). Plugin handlers are added in run.py.
	"""
	dispatch: Dispatch = {}

	topics_cfg = cfg.get("topics", {}) if isinstance(cfg, dict) else {}
	rtc_topic = str(topics_cfg.get("rtc", "spotter/utc-time"))

	# Wire up the RTC/clock handler if present
	rtc_handler = _load_core_rtc_handler()
	if rtc_handler:
		dispatch[rtc_topic] = rtc_handler
		logger.info("Registered core topic: %s -> %s", rtc_topic, rtc_handler.__name__)
	else:
		logger.warning("RTC topic '%s' present but no core handler was imported", rtc_topic)

	# Add other core topics here if you have them in the future
	# e.g. status, ping, etc.

	return dispatch

# Lifecycle hooks for core handlers (no-op safe defaults).
def init_handlers(handlers: Optional[Iterable[Any]] = None) -> Optional[dict]:
	"""
	Optionally return a dict to merge into the shared ctx in run.py.
	Keeping signature broad to be compatible with existing code.
	"""
	# If your clock module has an init() you want to call, do it here.
	return {}

def cleanup_handlers(handlers: Optional[Iterable[Any]] = None) -> None:
	"""
	Call per-handler cleanup if needed. Safe no-op by default.
	"""
	# If your clock module needs cleanup() call, add it here.
	return
