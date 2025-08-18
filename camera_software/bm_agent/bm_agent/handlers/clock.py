# import struct, subprocess, time
# from datetime import datetime, timezone
# 
# def _epoch_us_from_payload(data: bytes):
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
# 		self.apply_if_drift = int(cfg.get("apply_if_drift_seconds", 2))
# 		self.min_interval = int(cfg.get("min_apply_interval_seconds", 300))
# 		self.max_backward = int(cfg.get("max_backward_seconds", 0))
# 		self._last_apply = 0  # monotonic seconds
# 
# 	def _should_apply(self, drift_s: float) -> bool:
# 		now = time.monotonic()
# 		if abs(drift_s) < self.apply_if_drift:
# 			return False
# 		if (now - self._last_apply) < self.min_interval:
# 			return False
# 		if drift_s < 0 and abs(drift_s) > self.max_backward:
# 			# backwards move larger than allowed
# 			return False
# 		return True
# 
# 	def _apply(self, target_epoch_s: float) -> bool:
# 		# Call our privileged helper (created below)
# 		iso = datetime.fromtimestamp(target_epoch_s, tz=timezone.utc).isoformat()
# 		try:
# 			subprocess.run(
# 				["/usr/local/sbin/bm-set-time", iso],
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
# 		drift = target - now  # positive = system behind
# 
# 		print(f"[CLOCK] drift={drift:+.3f}s (target={datetime.utcfromtimestamp(target).isoformat()}Z)")
# 
# 		if not self._should_apply(drift):
# 			return
# 
# 		self._apply(target)
# 
# def init(ctx):
# 	ctx["clock"] = ClockSync(ctx["cfg"]["clock"])
# def cleanup(ctx):
# 	pass
# def handle(node_id, topic: str, data: bytes, ctx):
# 	ctx["clock"].handle(node_id, topic, data)
import struct, subprocess, time
from datetime import datetime, timezone

def _epoch_us_from_payload(data: bytes):
	# first 8 bytes = epoch µs (handles short + stamped payloads)
	if len(data) >= 8:
		(ts_us,) = struct.unpack("<Q", data[:8])
		# plausibility: 2000..2100
		if 946684800_000000 <= ts_us <= 4102444800_000000:
			return ts_us
	return None

class ClockSync:
	def __init__(self, cfg):
		self.enabled = bool(cfg.get("enabled", True))
		self.apply_if_drift = int(cfg.get("apply_if_drift_seconds", 2))   # only if |drift| > 2s
		self.min_interval = int(cfg.get("min_apply_interval_seconds", 300)) # at most once / 5 min
		self.max_backward = int(cfg.get("max_backward_seconds", 0))       # 0 = never step back
		self._last_apply = 0  # monotonic seconds

	def _should_apply(self, drift_s: float) -> bool:
		now = time.monotonic()
		if abs(drift_s) < self.apply_if_drift:
			return False
		if (now - self._last_apply) < self.min_interval:
			return False
		if drift_s < 0 and abs(drift_s) > self.max_backward:
			# backward move larger than allowed → skip
			return False
		return True

	def _apply(self, target_epoch_s: float) -> bool:
		iso = datetime.fromtimestamp(target_epoch_s, tz=timezone.utc).isoformat()
		try:
			# sudoers allows this exact helper without a password
			subprocess.run(
				["sudo", "/usr/local/sbin/bm-set-time", iso],
				check=True,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				text=True,
			)
			self._last_apply = time.monotonic()
			print(f"[CLOCK] set-time to {iso}")
			return True
		except subprocess.CalledProcessError as e:
			print(f"[CLOCK][ERROR] helper failed: {e.stderr.strip() or e}")
			return False

	def handle(self, node_id, topic: str, data: bytes):
		if not self.enabled:
			return
		ts_us = _epoch_us_from_payload(data)
		if ts_us is None:
			print(f"[CLOCK] unrecognized payload; skipping")
			return

		target = ts_us / 1e6
		now = time.time()
		drift = target - now  # positive = system is behind

		print(f"[CLOCK] drift={drift:+.3f}s (target={datetime.utcfromtimestamp(target).isoformat()}Z)")

		if not self._should_apply(drift):
			return

		self._apply(target)

def init(ctx):
	# cfg injected by dispatcher; keep instance on ctx
	ctx["clock"] = ClockSync(ctx["cfg"]["clock"])

def cleanup(ctx):
	pass

def handle(node_id, topic: str, data: bytes, ctx):
	ctx["clock"].handle(node_id, topic, data)
