# 
# import struct, subprocess, time
# from datetime import datetime, timezone
# 
# def _epoch_us_from_payload(data: bytes):
# 	# first 8 bytes = epoch µs (handles short + stamped payloads)
# 	if len(data) >= 8:
# 		(ts_us,) = struct.unpack("<Q", data[:8])
# 		# plausibility: 2000..2100
# 		if 946684800_000000 <= ts_us <= 4102444800_000000:
# 			return ts_us
# 	return None
# 
# class ClockSync:
# 	def __init__(self, cfg):
# 		self.enabled = bool(cfg.get("enabled", True))
# 		self.apply_if_drift = int(cfg.get("apply_if_drift_seconds", 2))   # only if |drift| > 2s
# 		self.min_interval = int(cfg.get("min_apply_interval_seconds", 300)) # at most once / 5 min
# 		self.max_backward = int(cfg.get("max_backward_seconds", 0))       # 0 = never step back
# 		self._last_apply = 0  # monotonic seconds
# 
# 	def _should_apply(self, drift_s: float) -> bool:
# 		now = time.monotonic()
# 		if abs(drift_s) < self.apply_if_drift:
# 			return False
# 		if (now - self._last_apply) < self.min_interval:
# 			return False
# 		if drift_s < 0 and abs(drift_s) > self.max_backward:
# 			# backward move larger than allowed → skip
# 			return False
# 		return True
# 
# 	def _apply(self, target_epoch_s: float) -> bool:
# 		iso = datetime.fromtimestamp(target_epoch_s, tz=timezone.utc).isoformat()
# 		try:
# 			# sudoers allows this exact helper without a password
# 			subprocess.run(
# 				["sudo", "/usr/local/sbin/bm-set-time", iso],
# 				check=True,
# 				stdout=subprocess.PIPE,
# 				stderr=subprocess.PIPE,
# 				text=True,
# 			)
# 			self._last_apply = time.monotonic()
# 			print(f"[CLOCK] set-time to {iso}")
# 			return True
# 		except subprocess.CalledProcessError as e:
# 			print(f"[CLOCK][ERROR] helper failed: {e.stderr.strip() or e}")
# 			return False
# 
# 	def handle(self, node_id, topic: str, data: bytes):
# 		if not self.enabled:
# 			return
# 		ts_us = _epoch_us_from_payload(data)
# 		if ts_us is None:
# 			print(f"[CLOCK] unrecognized payload; skipping")
# 			return
# 
# 		target = ts_us / 1e6
# 		now = time.time()
# 		drift = target - now  # positive = system is behind
# 
# 		print(f"[CLOCK] drift={drift:+.3f}s (target={datetime.utcfromtimestamp(target).isoformat()}Z)")
# 
# 		if not self._should_apply(drift):
# 			return
# 
# 		self._apply(target)
# 
# def init(ctx):
# 	# cfg injected by dispatcher; keep instance on ctx
# 	ctx["clock"] = ClockSync(ctx["cfg"]["clock"])
# 
# def cleanup(ctx):
# 	pass
# 
# def handle(node_id, topic: str, data: bytes, ctx):
# 	ctx["clock"].handle(node_id, topic, data)

# # bm_daemon/agent/handlers/rtc.py
# import struct
# import logging
# from datetime import datetime, timezone
# 
# log = logging.getLogger("RTC")   # shows as [RTC]
# 
# def init(ctx):    # <-- add
# 	pass
# 
# def cleanup(ctx): # <-- add
# 	pass
# 
# def _plausible_epoch_us(val: int) -> bool:
# 	return 946684800_000000 <= val <= 4102444800_000000  # 2000..2100
# 
# def decode_epoch_dt_from_payload(data: bytes):
# 	if len(data) >= 8:
# 		(ts_us,) = struct.unpack("<Q", data[:8])
# 		if _plausible_epoch_us(ts_us):
# 			return datetime.fromtimestamp(ts_us / 1e6, tz=timezone.utc)
# 	return None
# 
# def handle(node_id, topic: str, data: bytes, ctx):
# 	dt = decode_epoch_dt_from_payload(data)
# 	if dt:
# 		log.info("ts=%s (µs since epoch)", dt.isoformat())
# 		if isinstance(ctx, dict):
# 			ctx["last_rtc_dt"] = dt
# 	else:
# 		log.warning("unknown payload: 0x%s", data.hex())




# 
# import struct
# import logging
# import subprocess
# from datetime import datetime, timezone
# 
# log = logging.getLogger("CLOCK")
# 
# def init(ctx):    pass
# def cleanup(ctx): pass
# 
# def _plausible_epoch_us(val: int) -> bool:
# 	return 946684800_000000 <= val <= 4102444800_000000
# 
# def _decode_epoch_dt_from_payload(data: bytes):
# 	if len(data) >= 8:
# 		(ts_us,) = struct.unpack("<Q", data[:8])
# 		if _plausible_epoch_us(ts_us):
# 			return datetime.fromtimestamp(ts_us / 1e6, tz=timezone.utc)
# 	return None
# 
# # def _set_system_time_utc(dt: datetime):
# # 	iso_z = dt.strftime("%Y-%m-%dT%H:%M:%SZ")  # explicit UTC
# # 	try:
# # 		# Prefer explicit UTC set; avoids local-time interpretation
# # 		subprocess.run(["sudo", "date", "-u", "-s", iso_z], check=True)
# # 		# Optional: persist to RTC if present
# # 		try:
# # 			subprocess.run(["sudo", "hwclock", "--systohc"], check=True)
# # 		except Exception:
# # 			pass
# # 		return True, "date -u -s"
# # 	except Exception as e1:
# # 		# Secondary: force system timezone to UTC then set local time
# # 		try:
# # 			subprocess.run(["sudo", "timedatectl", "set-timezone", "UTC"], check=True)
# # 			subprocess.run(["sudo", "timedatectl", "set-time", dt.strftime("%Y-%m-%d %H:%M:%S")], check=True)
# # 			return True, "timedatectl (UTC)"
# # 		except Exception as e2:
# # 			return False, f"{e1!r}; {e2!r}"
# def _set_system_time_utc(dt: datetime):
# 	"""
# 	Set the system clock in UTC using `date -u -s`.
# 	No hardware RTC writes. No timedatectl. Quiet and deterministic.
# 	"""
# 	if dt.tzinfo is None:
# 		dt = dt.replace(tzinfo=timezone.utc)
# 	iso_z = dt.strftime("%Y-%m-%dT%H:%M:%SZ")  # RFC3339-like
# 	# Requires privileges; if you're not root you'll get 'Operation not permitted'
# 	subprocess.run(["sudo", "date", "-u", "-s", iso_z], check=True)
# 	log.info("set-time to %s via date -u -s", dt.isoformat())
# 
# def handle(node_id, topic: str, data: bytes, ctx):
# 	# prefer time decoded by rtc.py (if it ran), else decode here
# 	dt = (ctx or {}).get("last_rtc_dt")
# 	if not dt:
# 		dt = _decode_epoch_dt_from_payload(data)
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
# 	apply_if   = float(clk_cfg.get("apply_if_drift_seconds", 1.0))
# 	max_back   = float(clk_cfg.get("max_backward_seconds", 0.0))
# 	min_intvl  = float(clk_cfg.get("min_apply_interval_seconds", 11.0))
# 
# 	import time
# 	now_mono = time.monotonic()
# 	last = (ctx or {}).get("last_clock_apply_ts", 0.0)
# 
# 	if abs(drift) < apply_if or (now_mono - last) < min_intvl:
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

# bm_daemon/agent/handlers/clock.py
from __future__ import annotations
import logging
import struct
import subprocess
import time
from datetime import datetime, timezone
from typing import Optional

# Match your unified log style (e.g., 2025-...Z [RTC] [INFO] ...)
LOG_RTC = logging.getLogger("RTC")
LOG     = logging.getLogger("CLOCK")

# throttle state
_last_apply_mono: Optional[float] = None


def init(ctx):
	"""Prepare per-run state."""
	global _last_apply_mono
	_last_apply_mono = None
	ctx.setdefault("clock", {})


def cleanup(ctx):
	"""Nothing to clean up."""
	pass


def _decode_epoch_dt_from_payload(data: bytes) -> Optional[datetime]:
	"""
	Payload format: first 8 bytes = little-endian uint64 of microseconds since Unix epoch (UTC).
	Returns a timezone-aware datetime in UTC, or None if implausible.
	"""
	if len(data) >= 8:
		(ts_us,) = struct.unpack("<Q", data[:8])
		# Plausible range ~ 2000..2100 to avoid junk
		if 946684800_000000 <= ts_us <= 4102444800_000000:
			return datetime.fromtimestamp(ts_us / 1e6, tz=timezone.utc)
	return None


def _utc_now() -> datetime:
	return datetime.now(timezone.utc)


def _set_system_time_utc(dt: datetime):
	"""
	Set the system clock in UTC using `date -u -s`.
	NOTE: Requires privileges (run agent with sudo or as a service with proper perms).
	"""
	if dt.tzinfo is None:
		dt = dt.replace(tzinfo=timezone.utc)
	iso_z = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
	subprocess.run(["sudo", "date", "-u", "-s", iso_z], check=True)
	LOG.info("set-time to %s via date -u -s", dt.isoformat())


def _should_apply(drift_s: float, cfg: dict) -> bool:
	"""
	Decide whether to apply a time step:
	  - only if |drift| >= apply_if_drift_seconds
	  - and at most once per min_apply_interval_seconds
	"""
	global _last_apply_mono
	thr = float(cfg.get("apply_if_drift_seconds", 1.0))
	min_interval = float(cfg.get("min_apply_interval_seconds", 10.0))

	if abs(drift_s) < thr:
		return False

	now_mono = time.monotonic()
	if _last_apply_mono is not None and (now_mono - _last_apply_mono) < min_interval:
		return False

	return True


def handle(node_id, topic: str, data: bytes, ctx):
	"""
	Main handler for `spotter/utc-time`.
	Decodes the incoming timestamp, logs it, computes drift, and conditionally steps system time.
	"""
	cfg_clock = (ctx.get("cfg") or {}).get("clock", {}) or {}
	if not cfg_clock.get("enabled", True):
		return

	# 1) Decode RTC message
	dt = _decode_epoch_dt_from_payload(data)
	if not dt:
		LOG_RTC.warning("unknown payload: 0x%s", data.hex())
		return

	LOG_RTC.info("ts=%s (µs since epoch)", dt.isoformat())

	# 2) Compute drift (positive => system is behind target)
	now = _utc_now()
	drift_s = (dt - now).total_seconds()
	LOG.info("drift=%+.3fs (target=%s)", drift_s, dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))

	# 3) Decide whether to apply
	if not _should_apply(drift_s, cfg_clock):
		return

	# 4) Backward-step policy
	max_back = float(cfg_clock.get("max_backward_seconds", 0.0))
	if drift_s < 0:
		if max_back <= 0.0:
			LOG.info("skip backward set (policy: max_backward_seconds=0)")
			return
		if abs(drift_s) > max_back:
			LOG.info(
				"skip backward set (would move back %.1fs > max_backward_seconds=%.1f)",
				abs(drift_s), max_back
			)
			return

	# 5) Apply
	try:
		_set_system_time_utc(dt)
		global _last_apply_mono
		_last_apply_mono = time.monotonic()
	except Exception as e:
		LOG.error("failed to set time: %r", e)
 