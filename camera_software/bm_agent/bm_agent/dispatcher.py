# bm_agent/dispatcher.py
from __future__ import annotations
from typing import Callable, Dict, Any
from .handlers import rtc, clock

Handler = Callable[[int, str, bytes, dict], None]

def init_handlers(cfg: dict) -> dict:
	ctx: dict[str, Any] = {"cfg": cfg}
	# Diagnostics: show exactly which handler modules got imported.
	try:
		print(f"[PATH] rtc module:   {rtc.__file__}")
		print(f"[PATH] clock module: {clock.__file__}")
	except Exception:
		pass

	# Prefer module-level init() if present; otherwise construct ClockSync directly.
	if hasattr(clock, "init"):
		clock.init(ctx)
	else:
		print("[WARN] handlers.clock has no init(); constructing ClockSync directly")
		if hasattr(clock, "ClockSync"):
			ctx["clock"] = clock.ClockSync(cfg.get("clock", {}))
		else:
			raise RuntimeError("handlers.clock missing both init() and ClockSync")
	return ctx

def cleanup_handlers(ctx: dict) -> None:
	try:
		if hasattr(clock, "cleanup"):
			clock.cleanup(ctx)
	except Exception:
		pass

def build_dispatch(cfg: dict) -> Dict[str, Handler]:
	topics = cfg.get("topics", {})
	rtc_topic = topics.get("rtc")
	dispatch: Dict[str, Handler] = {}
	if rtc_topic:
		def _rtc_and_clock(node_id: int, topic: str, data: bytes, ctx: dict) -> None:
			rtc.handle(node_id, topic, data, ctx)     # [RTC] pretty-print
			clock.handle(node_id, topic, data, ctx)   # [CLOCK] sync logic
		dispatch[str(rtc_topic)] = _rtc_and_clock
	return dispatch
