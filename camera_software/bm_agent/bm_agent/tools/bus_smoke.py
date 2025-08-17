# bm_agent/tools/bus_smoke.py
from __future__ import annotations
import argparse, time
from pathlib import Path
from datetime import datetime, timezone

try:
	import yaml
except Exception:
	yaml = None

from bm_agent.bus import open_bus, subscribe_one

PLAUSIBLE_MIN = 946684800_000000   # 2000-01-01 UTC in µs
PLAUSIBLE_MAX = 4102444800_000000  # 2100-01-01 UTC in µs

def _plausible(us: int) -> bool:
	return PLAUSIBLE_MIN <= us <= PLAUSIBLE_MAX

def _decode_epoch_us(data: bytes) -> int | None:
	if len(data) < 8:
		return None
	head = int.from_bytes(data[:8], "little")
	tail = int.from_bytes(data[-8:], "little") if len(data) >= 16 else None
	cand = [x for x in (head, tail) if x is not None and _plausible(x)]
	return max(cand) if cand else None

def _on_msg(node_id: int, topic, data: bytes):
	t = topic.decode() if isinstance(topic, (bytes, bytearray)) else str(topic)
	print(f"[RX] node=0x{node_id:016x} topic={t!r} len={len(data)}")
	ts_us = _decode_epoch_us(data)
	if ts_us is not None:
		dt = datetime.fromtimestamp(ts_us / 1e6, tz=timezone.utc)
		print(f"[RX] epoch_us={ts_us} -> {dt.isoformat()}")
	else:
		print(f"[RX] payload(hex first 32)={data[:16].hex()}")

def _load_topic_from_config() -> str | None:
	if not yaml:
		return None
	# project root = two parents up from this file
	cfg_path = Path(__file__).resolve().parents[2] / "config.yaml"
	if not cfg_path.exists():
		return None
	cfg = yaml.safe_load(cfg_path.read_text()) or {}
	return (cfg.get("topics") or {}).get("rtc")

def main():
	ap = argparse.ArgumentParser(description="Simple Bristlemouth foreground smoke test")
	ap.add_argument("--topic", help="Topic to subscribe to (default: topics.rtc from config.yaml or 'spotter/utc-time')")
	ap.add_argument("--duration", type=int, default=30, help="How many seconds to listen")
	args = ap.parse_args()

	topic = args.topic or _load_topic_from_config() or "spotter/utc-time"
	print(f"[SMOKE] topic={topic!r} duration={args.duration}s")

	bm = open_bus()  # prints port info and configures timeouts
	try:
		subscribe_one(bm, topic, _on_msg)
		deadline = time.monotonic() + args.duration
		while time.monotonic() < deadline:
			bm.bristlemouth_process(0.1)  # drives callbacks
	finally:
		try:
			print("[SMOKE] closing UART…")
			if getattr(bm, "uart", None) and bm.uart.is_open:
				try:
					bm.uart.flush()
				except Exception:
					pass
				bm.uart.close()
		finally:
			print("[SMOKE] done.")

if __name__ == "__main__":
	main()
