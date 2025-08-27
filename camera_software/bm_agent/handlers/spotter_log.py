# bm_agent/handlers/spotter_log.py
from __future__ import annotations
from typing import Any

# Keep lines modest so Spotter’s UI doesn’t wrap weirdly
_MAX_LEN = 180

def _human_bytes(n: int) -> str:
	try:
		n = int(n)
	except Exception:
		return str(n)
	for unit in ("B","KB","MB","GB"):
		if n < 1024 or unit == "GB":
			return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
		n /= 1024.0

def _human_bitrate(bps: int) -> str:
	try:
		bps = float(bps)
	except Exception:
		return str(bps)
	if bps >= 1_000_000:
		return f"{bps/1_000_000:.1f}Mb/s"
	if bps >= 1_000:
		return f"{bps/1_000:.1f}kb/s"
	return f"{int(bps)}b/s"

def _fmt_kv(k: str, v: Any) -> str:
	if k in {"bytes", "size"}:
		return f"size={_human_bytes(v)}"
	if k in {"br", "bitrate"}:
		return f"br={_human_bitrate(v)}"
	if k in {"dur", "dur_s"}:
		try:
			fv = float(v)
			# print clean “5s” not “5.0s”
			return f"dur={int(fv)}s" if abs(fv - int(fv)) < 1e-6 else f"dur={fv:.1f}s"
		except Exception:
			return f"dur={v}"
	return f"{k}={v}"

def spotter_log(ctx: dict, level: str, tag: str, msg: str, **fields):
	"""
	Send a single, human-friendly line to Spotter terminal using ctx['bm'].spotter_print.
	  level: "INFO" | "ERR" | "WARN" | "DEBUG"
	  tag:   short subsystem tag, e.g. "CAM"
	  msg:   action/result like "video saved" or "image failed"
	  fields: key/values to render in consistent order
	"""
	bm = (ctx or {}).get("bm")
	line = f"[{tag}] [{level}] {msg}"

	if fields:
		# preserve the insertion order of kwargs (Py3.7+), join as k=v
		kv = " ".join(_fmt_kv(k, v) for k, v in fields.items())
		line = f"{line} {kv}"

	if len(line) > _MAX_LEN:
		line = line[:_MAX_LEN]

	if bm and hasattr(bm, "spotter_print"):
		try:
			bm.spotter_print(line)
			return
		except Exception as e:
			print(f"[SPOTTER_LOG][WARN] publish failed: {e!r}")

	# Fallback to console if no bm or failure
	print("[SPOTTER]", line)
