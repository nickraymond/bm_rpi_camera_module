# bm_agent/handlers/rtc.py
from __future__ import annotations
import struct
from datetime import datetime, timezone

def _plausible_epoch_us(v: int) -> bool:
	return 946684800_000000 <= v <= 4102444800_000000  # 2000..2100

def decode_epoch_dt_from_payload(data: bytes) -> datetime | None:
	# Works for 8B and longer stamped payloads; prefer the newest 8B (tail) if available.
	if len(data) >= 16:
		(tail_us,) = struct.unpack("<Q", data[-8:])
		if _plausible_epoch_us(tail_us):
			return datetime.fromtimestamp(tail_us / 1e6, tz=timezone.utc)
	if len(data) >= 8:
		(head_us,) = struct.unpack("<Q", data[:8])
		if _plausible_epoch_us(head_us):
			return datetime.fromtimestamp(head_us / 1e6, tz=timezone.utc)
	return None

def handle(node_id: int, topic: str, data: bytes, ctx: dict) -> None:
	dt = decode_epoch_dt_from_payload(data)
	if dt:
		print(f"[RTC] node={node_id} topic={topic} {dt.isoformat()}")
	else:
		print(f"[RTC] node={node_id} topic={topic} unknown payload len={len(data)}")
