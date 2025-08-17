# bm_agent/handlers/clock.py
from __future__ import annotations
import struct, subprocess, time
from datetime import datetime, timezone

def _plausible_epoch_us(v: int) -> bool:
	return 946684800_000000 <= v <= 4102444800_000000  # 2000..2100 (µs)

def _epoch_us_from_payload(data: bytes) -> int | None:
	cand = []
	if len(data) >= 8:
		(head_us,) = struct.unpack("<Q", data[:8])
		if _plausible_epoch_us(head_us):
			cand.append(head_us)
	if len(data) >= 16:
		(tail_us,) = struct.unpack("<Q", data[-8:])
		if _plausible_epoch_us(tail_us):
			cand.append(tail_us)
	if not cand:
		return None
	return max(cand)

class ClockSync:
	def __init__(self, cfg: dict):
		self.apply_if_drift_s = float(cfg.get("apply_if_drift_seconds", 0.3))
		self.min_apply_interval_s = float(cfg.get("min_apply_interval_seconds", 300))
		self.max_backward_s = float(cfg.get("max_backward_seconds", 0))
		self.apply_immediately_on_boot = bool(cfg.get("apply_immediately_on_boot", True))
		self._last_apply_monotonic = 0.0
		self._did_first = False

	def _apply_system_clock(self, target_dt: datetime) -> None:
		iso = target_dt.strftime("%Y-%m-%d %H:%M:%S")
		subprocess.run(["/bin/date", "-u", "-s", iso], check=False)
		subprocess.run(["/sbin/hwclock", "-w"], check=False)
		print(f"[CLOCK] set system time -> {target_dt.isoformat()}")

	def maybe_sync(self, ts_us: int) -> None:
		target_dt = datetime.fromtimestamp(ts_us / 1e6, tz=timezone.utc)
		now = datetime.now(timezone.utc)
		drift_s = abs((target_dt - now).total_seconds())
		now_mono = time.monotonic()
		too_soon = (now_mono - self._last_apply_monotonic) < self.min_apply_interval_s
		backward_s = (now - target_dt).total_seconds()
		if backward_s > self.max_backward_s:
			print(f"[CLOCK] refused to move backward by {backward_s:.3f}s (> {self.max_backward_s}s)")
			return
		if drift_s >= self.apply_if_drift_s and (self._did_first or not too_soon or self.apply_immediately_on_boot):
			self._apply_system_clock(target_dt)
			self._last_apply_monotonic = now_mono
			self._did_first = True
		else:
			print(f"[CLOCK] drift={drift_s:.3f}s (no apply)")

# ---- dispatcher glue ----

def init(ctx):
	clock_cfg = ctx.get("cfg", {}).get("clock", {})
	ctx["clock"] = ClockSync(clock_cfg)

def cleanup(ctx):
	pass

def handle(node_id: int, topic: str, data: bytes, ctx: dict) -> None:
	ts_us = _epoch_us_from_payload(data)
	if ts_us is None:
		print(f"[CLOCK] unrecognized payload: len={len(data)} hex={data[:16].hex()}...")
		return
	clk: ClockSync = ctx["clock"]
	clk.maybe_sync(ts_us)
