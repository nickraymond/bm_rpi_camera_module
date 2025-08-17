# #!/usr/bin/env python3
# from __future__ import annotations
# import os, sys, signal, traceback
# 
# # Ensure project root is on sys.path when run by systemd
# PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
# if PROJECT_ROOT not in sys.path:
# 	sys.path.insert(0, PROJECT_ROOT)
# 
# from bm_agent.dispatcher import build_dispatch, init_handlers, cleanup_handlers
# 
# _running = True
# def _term(*_):
# 	global _running
# 	_running = False
# 
# signal.signal(signal.SIGTERM, _term)
# signal.signal(signal.SIGINT, _term)
# 
# def _norm_topic(x) -> str:
# 	"""
# 	Normalize a topic to a clean str:
# 	  - bytes/bytearray -> UTF-8 string
# 	  - stringified bytes like "b'foo/bar'" or 'b"foo/bar"' -> extract inner
# 	  - strip trailing NULs
# 	"""
# 	if isinstance(x, (bytes, bytearray)):
# 		s = x.decode("utf-8", errors="replace")
# 	else:
# 		s = str(x)
# 	s = s.rstrip("\x00")
# 	if len(s) >= 3 and s[0] == "b" and s[1] in ("'", '"') and s[-1] in ("'", '"'):
# 		s = s[2:-1]
# 	return s
# 
# def main() -> int:
# 	print("[START] bm-agent starting…")
# 	print(f"[PATH] sys.executable={sys.executable}")
# 	print(f"[PATH] cwd={os.getcwd()}")
# 	# Print import paths for sanity
# 	try:
# 		import bm_agent.dispatcher as disp
# 		import bm_agent.handlers.rtc as rtc
# 		import bm_agent.handlers.clock as clock
# 		print(f"[PATH] dispatcher: {getattr(disp, '__file__', '?')}")
# 		print(f"[PATH] rtc:        {getattr(rtc, '__file__', '?')}")
# 		print(f"[PATH] clock:      {getattr(clock, '__file__', '?')}")
# 	except Exception:
# 		print("[WARN] failed to print module paths")
# 		traceback.print_exc()
# 
# 	# --- Load config
# 	try:
# 		# Minimal inline loader to avoid cross-file drift
# 		import yaml
# 		with open(os.path.join(PROJECT_ROOT, "config.yaml"), "r") as f:
# 			cfg = yaml.safe_load(f) or {}
# 		print(f"[CFG] loaded topics={cfg.get('topics', {})}")
# 	except Exception:
# 		print("[FATAL] failed to load config.yaml")
# 		traceback.print_exc()
# 		return 2
# 
# 	# --- Init handlers and dispatch
# 	try:
# 		ctx = init_handlers(cfg)
# 		dispatch = build_dispatch(cfg)
# 		# sanity: normalize keys
# 		dispatch = { _norm_topic(k): v for k, v in dispatch.items() }
# 		print(f"[DISPATCH] topics={list(dispatch.keys()) or []}")
# 		if not dispatch:
# 			print("[WARN] no topics registered; agent will idle.")
# 	except Exception:
# 		print("[FATAL] failed to build dispatch/handlers")
# 		traceback.print_exc()
# 		return 2
# 
# 	# --- Open BM bus (replace with your bus impl)
# 	try:
# 		# You had these helpers in your repo; keep signature the same
# 		from bm_agent.bus import open_bus, subscribe_many, loop
# 		uart = cfg.get("uart_device", "/dev/serial0")
# 		baud = int(cfg.get("baudrate", 115200))
# 		bm = open_bus(uart, baud)
# 		print(f"[BUS] open ok uart={uart} baud={baud}")
# 	except Exception:
# 		print("[FATAL] failed to open bus")
# 		traceback.print_exc()
# 		return 2
# 
# 	def _on_msg(node_id, topic, payload):
# 		try:
# 			t = _norm_topic(topic)
# 			h = dispatch.get(t)
# 			if h is None:
# 				print(f"[WARN] no handler for topic={t!r} (raw={topic!r})")
# 				return
# 			h(int(node_id), t, bytes(payload), ctx)
# 		except Exception:
# 			print("[HANDLER][ERROR] exception in handler:")
# 			traceback.print_exc()
# 
# 	try:
# 		subscribe_many(bm, list(dispatch.keys()), _on_msg)
# 		print("[RUN] bm-agent started")
# 		loop(bm, lambda: not _running)
# 		print("[RUN] bm-agent loop exited")
# 	except Exception:
# 		print("[FATAL] loop crashed")
# 		traceback.print_exc()
# 		return 2
# 	finally:
# 		try:
# 			cleanup_handlers(ctx)
# 		except Exception:
# 			pass
# 		print("[EXIT] bm-agent stopped")
# 
# 	return 0
# 
# if __name__ == "__main__":
# 	sys.exit(main())

#!/usr/bin/env python3
from __future__ import annotations
import os, sys, signal, traceback, time

# Ensure project root is on sys.path when run by systemd
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
	sys.path.insert(0, PROJECT_ROOT)

from bm_agent.dispatcher import build_dispatch, init_handlers, cleanup_handlers

_running = True
def _term(*_):
	global _running
	_running = False

signal.signal(signal.SIGTERM, _term)
signal.signal(signal.SIGINT, _term)

def _norm_topic(x) -> str:
	"""
	Normalize a topic to a clean str:
	  - bytes/bytearray -> UTF-8 string
	  - stringified bytes like "b'foo/bar'" or 'b"foo/bar"' -> extract inner
	  - strip trailing NULs
	"""
	if isinstance(x, (bytes, bytearray)):
		s = x.decode("utf-8", errors="replace")
	else:
		s = str(x)
	s = s.rstrip("\x00")
	if len(s) >= 3 and s[0] == "b" and s[1] in ("'", '"') and s[-1] in ("'", '"'):
		s = s[2:-1]
	return s

def safe_close_bus(bm) -> None:
	"""Best-effort close of the BristlemouthSerial and its underlying pyserial port."""
	try:
		print("[BUS] closing…")
		# 1) If the wrapper has a close/safe_close, use it
		for meth in ("safe_close", "close", "shutdown"):
			fn = getattr(bm, meth, None)
			if callable(fn):
				try:
					fn()
				except Exception:
					pass
				# continue to deep-close uart below just to be extra safe
		# 2) Deep-close the underlying pyserial.Serial if present
		uart = getattr(bm, "uart", None)
		if uart is not None:
			try:
				if hasattr(uart, "cancel_write"): 
					try: uart.cancel_write()
					except Exception: pass
				if hasattr(uart, "cancel_read"): 
					try: uart.cancel_read()
					except Exception: pass
				try: uart.reset_output_buffer()
				except Exception: pass
				try: uart.reset_input_buffer()
				except Exception: pass
				try: uart.flush()
				except Exception: pass
				try:
					if hasattr(uart, "dtr"): uart.dtr = False
					if hasattr(uart, "rts"): uart.rts = False
				except Exception:
					pass
				try: uart.close()
				except Exception: 
					pass
			except Exception:
				pass
		# tiny pause helps some kernels release the file handle
		time.sleep(0.1)
		print("[BUS] closed")
	except Exception:
		# never let close path crash the shutdown
		pass

def main() -> int:
	print("[START] bm-agent starting…")
	print(f"[PATH] sys.executable={sys.executable}")
	print(f"[PATH] cwd={os.getcwd()}")
	# Print import paths for sanity
	try:
		import bm_agent.dispatcher as disp
		import bm_agent.handlers.rtc as rtc
		import bm_agent.handlers.clock as clock
		print(f"[PATH] dispatcher: {getattr(disp, '__file__', '?')}")
		print(f"[PATH] rtc:        {getattr(rtc, '__file__', '?')}")
		print(f"[PATH] clock:      {getattr(clock, '__file__', '?')}")
	except Exception:
		print("[WARN] failed to print module paths")
		traceback.print_exc()

	# --- Load config
	try:
		import yaml
		with open(os.path.join(PROJECT_ROOT, "config.yaml"), "r") as f:
			cfg = yaml.safe_load(f) or {}
		print(f"[CFG] loaded topics={cfg.get('topics', {})}")
	except Exception:
		print("[FATAL] failed to load config.yaml")
		traceback.print_exc()
		return 2

	bm = None
	ctx = None
	try:
		# --- Init handlers and dispatch
		ctx = init_handlers(cfg)
		dispatch = build_dispatch(cfg)
		dispatch = { _norm_topic(k): v for k, v in dispatch.items() }
		print(f"[DISPATCH] topics={list(dispatch.keys()) or []}")

		# --- Open BM bus
		from bm_agent.bus import open_bus, subscribe_many, loop
		uart = cfg.get("uart_device", "/dev/serial0")
		baud = int(cfg.get("baudrate", 115200))
		bm = open_bus(uart, baud)
		print(f"[BUS] open ok uart={uart} baud={baud}")

		# --- subscribe, then loop
		def _on_msg(node_id, topic, payload):
			try:
				t = _norm_topic(topic)
				h = dispatch.get(t)
				if h is None:
					print(f"[WARN] no handler for topic={t!r} (raw={topic!r})")
					return
				h(int(node_id), t, bytes(payload), ctx)
			except Exception:
				print("[HANDLER][ERROR] exception in handler:")
				traceback.print_exc()

		# If we crash during subscribe, safe_close_bus(bm) in finally will run
		for t in list(dispatch.keys()):
			print(f"[SUB] subscribing to {t!r}")
		# subscribe_many(bm, list(dispatch.keys()), _on_msg)
		
		# Subscribe only to the RTC topic (back to basics)
		rtc_topic = cfg.get("topics", {}).get("rtc")
		if not rtc_topic:
			raise RuntimeError("No RTC topic configured in config.yaml (topics.rtc)")
		from bm_agent.bus import subscribe_one
		subscribe_one(bm, rtc_topic, _on_msg)
		

		print("[RUN] bm-agent started")
		loop(bm, lambda: not _running)
		print("[RUN] bm-agent loop exited")
		return 0

	except Exception:
		print("[FATAL] loop crashed")
		traceback.print_exc()
		return 2

	finally:
		# Always close the serial bus (even if subscribe failed)
		try:
			if bm is not None:
				safe_close_bus(bm)
		except Exception:
			pass
		try:
			if ctx is not None:
				cleanup_handlers(ctx)
		except Exception:
			pass
		print("[EXIT] bm-agent stopped")

if __name__ == "__main__":
	sys.exit(main())

