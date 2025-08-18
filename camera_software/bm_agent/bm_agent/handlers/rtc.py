import struct
from datetime import datetime, timezone

def _plausible_epoch_us(val: int) -> bool:
	return 946684800_000000 <= val <= 4102444800_000000  # 2000..2100

def decode_epoch_dt_from_payload(data: bytes):
	# Works for short (8B) and stamped (>=8B) payloads
	if len(data) >= 8:
		(ts_us,) = struct.unpack("<Q", data[:8])
		if _plausible_epoch_us(ts_us):
			return datetime.fromtimestamp(ts_us / 1e6, tz=timezone.utc)
	return None

def handle(node_id, topic: str, data: bytes, ctx):
	dt = decode_epoch_dt_from_payload(data)
	if dt:
		print(f"[RTC] {dt.isoformat()} (µs since epoch)")
	else:
		print(f"[RTC] unknown payload: 0x{data.hex()}")
