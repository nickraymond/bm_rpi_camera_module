# import struct
# from datetime import datetime, timezone
# 
# def _plausible_epoch_us(val: int) -> bool:
# 	return 946684800_000000 <= val <= 4102444800_000000  # 2000..2100
# 
# def decode_epoch_dt_from_payload(data: bytes):
# 	# Works for short (8B) and stamped (>=8B) payloads
# 	if len(data) >= 8:
# 		(ts_us,) = struct.unpack("<Q", data[:8])
# 		if _plausible_epoch_us(ts_us):
# 			return datetime.fromtimestamp(ts_us / 1e6, tz=timezone.utc)
# 	return None
# 
# def handle(node_id, topic: str, data: bytes, ctx):
# 	dt = decode_epoch_dt_from_payload(data)
# 	if dt:
# 		print(f"[RTC] {dt.isoformat()} (µs since epoch)")
# 	else:
# 		print(f"[RTC] unknown payload: 0x{data.hex()}")

# bm_daemon/agent/handlers/clock.py
# import logging
# import subprocess
# from datetime import datetime, timezone
# 
# log = logging.getLogger("CLOCK")  # shows as [CLOCK]
# 
# def init(ctx):    # <-- add
# 	pass
# 
# def cleanup(ctx): # <-- add
# 	pass
# 
# def _set_system_time_utc(dt: datetime):
# 	iso = dt.strftime("%Y-%m-%d %H:%M:%S")
# 	try:
# 		subprocess.run(["sudo", "timedatectl", "set-time", iso], check=True)
# 		return True, "timedatectl"
# 	except Exception:
# 		try:
# 			subprocess.run(["sudo", "date", "-u", "-s", dt.strftime("%Y-%m-%dT%H:%M:%S")], check=True)
# 			return True, "date -u -s"
# 		except Exception as e:
# 			return False, repr(e)
# 
# def handle(node_id, topic: str, data: bytes, ctx):
# 	# Prefer the time decoded by rtc.py; fall back to decoding here.
# 	dt = (ctx or {}).get("last_rtc_dt")
# 	if not dt:
# 		from .rtc import decode_epoch_dt_from_payload
# 		dt = decode_epoch_dt_from_payload(data)
# 
# 	if not dt:
# 		log.warning("no valid RTC time available")
# 		return
# 
# 	now = datetime.now(timezone.utc)
# 	drift = (dt - now).total_seconds()
# 	log.info("drift=%+.3fs (target=%s)", drift, dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
# 
# 	clk_cfg = ((ctx or {}).get("cfg") or {}).get("clock", {}) or {}
# 	apply_if = float(clk_cfg.get("apply_if_drift_seconds", 1.0))
# 	max_back = float(clk_cfg.get("max_backward_seconds", 0.0))
# 	min_interval = float(clk_cfg.get("min_apply_interval_seconds", 11.0))
# 
# 	import time
# 	now_mono = time.monotonic()
# 	last = (ctx or {}).get("last_clock_apply_ts", 0.0)
# 
# 	if abs(drift) < apply_if or (now_mono - last) < min_interval:
# 		return
# 	if drift < 0 and max_back <= 0:
# 		return
# 
# 	ok, how = _set_system_time_utc(dt)
# 	if ok:
# 		if isinstance(ctx, dict):
# 			ctx["last_clock_apply_ts"] = now_mono
# 		log.info("set-time to %s via %s", dt.isoformat(), how)
# 	else:
# 		log.error("set-time failed: %s", how)

import struct
import logging
from datetime import datetime, timezone

log = logging.getLogger("RTC")

def init(ctx):    pass
def cleanup(ctx): pass

def _plausible_epoch_us(val: int) -> bool:
	return 946684800_000000 <= val <= 4102444800_000000  # 2000..2100

def decode_epoch_dt_from_payload(data: bytes):
	if len(data) >= 8:
		(ts_us,) = struct.unpack("<Q", data[:8])
		if _plausible_epoch_us(ts_us):
			return datetime.fromtimestamp(ts_us / 1e6, tz=timezone.utc)
	return None

def handle(node_id, topic: str, data: bytes, ctx):
	dt = decode_epoch_dt_from_payload(data)
	if dt:
		log.info("ts=%s (µs since epoch)", dt.isoformat())
		if isinstance(ctx, dict):
			ctx["last_rtc_dt"] = dt
	else:
		log.warning("unknown payload: 0x%s", data.hex())
