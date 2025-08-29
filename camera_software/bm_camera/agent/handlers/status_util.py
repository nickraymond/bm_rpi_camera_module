# bm_agent/handlers/status_util.py
from pathlib import Path
from bm_camera.common.config import get_status_topic
from ..publish import pub_text



# Try to use your existing publish helper if present.
try:
	from bm_camera.agent.publish import pub_text as _pub_text
except Exception:
	_pub_text = None

def _status_topic(ctx) -> str:
	cfg = ctx.get("cfg", {}) if ctx else {}
	return cfg.get("topics", {}).get("camera_status", "camera/status")

# def send_status(ctx, kind: str, **fields):
# 	"""
# 	Send a simple text status line: e.g., "OK op=video file=VID_....mp4 res=720p dur=5 fps=25".
# 	Falls back to print if publishing isn't available.
# 	"""
# 	topic = _status_topic(ctx)
# 	parts = [kind] + [f"{k}={v}" for k, v in fields.items()]
# 	payload = " ".join(parts)
# 
# 	bm = ctx.get("bm") if ctx else None
# 	if bm and _pub_text:
# 		try:
# 			_pub_text(bm, topic, payload, version=0)   # text, ver=0
# 			return
# 		except Exception as e:
# 			print(f"[STATUS][WARN] publish failed: {e!r}")
# 	# Fallback to console
# 	print(f"[STATUS] {topic} :: {payload}")
def send_status(ctx, kind: str, **fields):
	"""
	Send status both to the Spotter terminal (human-readable) and to the status topic.
	- Terminal: bm.spotter_print("[ACK] ...")  -> shows up immediately on Spotter CLI
	- Topic:    pub_text(bm, "camera/status", "...")  -> for downstream subscribers
	Falls back to printing locally if publishing is unavailable.
	"""
	topic = get_status_topic()
	parts = [kind] + [f"{k}={v}" for k, v in fields.items()]
	text_line = " ".join(parts)
	
	bm = ctx.get("bm") if ctx else None
	
	# 1) Always try to print a human-friendly line to Spotter terminal.
	#    (This is independent of the status topic.)
	if bm and hasattr(bm, "spotter_print"):
		try:
			bm.spotter_print(f"[ACK] {text_line}")
		except Exception as e:
			print(f"[STATUS][WARN] spotter_print failed: {e!r}")
	
	# 2) Also try to publish to the status topic (if helper is available)
	if bm:
		try:
			from bm_camera.agent.publish import pub_text  # updated import path
			pub_text(bm, topic, text_line)  # type=TEXT on camera/status
			return
		except Exception as e:
			print(f"[STATUS][WARN] pub_text unavailable: {e!r}")
	
	# 3) Fallback to console (no UART or no helpers)
	print(f"[STATUS] {topic} :: {text_line}")

# bm_agent/handlers/status_util.py
def ack_print(ctx, message: str):
	"""
	Print an ACK/ERR line on the Spotter/Bridge console using bm.spotter_print().
	Falls back to console print if bm is not available.
	"""
	bm = ctx.get("bm") if ctx else None
	if bm and hasattr(bm, "spotter_print"):
		try:
			bm.spotter_print(message)
			return
		except Exception as e:
			print(f"[ACK][WARN] spotter_print failed: {e!r}")
	# Fallback (still see something in the Pi logs)
	print(f"[ACK] {message}")