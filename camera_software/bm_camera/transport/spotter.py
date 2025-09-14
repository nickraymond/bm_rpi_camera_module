
# bm_camera/transport/spotter.py
import base64, os, time, logging
from pathlib import Path

logger = logging.getLogger("TX")

def build_base64_chunks(path: Path, *, chunk_size=300):
	"""
	Returns (basename, chunks, byte_len). DEBUG logs include input size,
	base64 length, and chunk count.
	"""
	path = Path(path)
	raw_bytes = path.read_bytes()
	byte_len = len(raw_bytes)
	b64 = base64.b64encode(raw_bytes).decode("ascii")
	total_len = len(b64)
	chunks = [b64[i:i+chunk_size] for i in range(0, total_len, chunk_size)]

	if logger.isEnabledFor(logging.DEBUG):
		logger.debug(
			"[CHUNK] file=%s bytes=%d b64_len=%d chunk_size=%d chunks=%d",
			path.name, byte_len, total_len, chunk_size, len(chunks)
		)
	return path.name, chunks, byte_len


def mirror_chunks_to_buffer(chunks, clear_first=True, *, buffer_dir="/home/pi/bm_camera/camera_software/buffer"):
	"""
	Mirrors chunks to buffer/ for troubleshooting; DEBUG logs only.
	"""
	from pathlib import Path
	import shutil
	bdir = Path(buffer_dir)
	if clear_first and bdir.exists():
		shutil.rmtree(bdir)
	bdir.mkdir(parents=True, exist_ok=True)

	for i, c in enumerate(chunks):
		(bdir / f"split_{i}.txt").write_text(c)

	if logger.isEnabledFor(logging.DEBUG):
		logger.debug("[CHUNK] mirrored %d chunks to %s", len(chunks), bdir)

# def send_chunks_to_spotter(bm, *, file_label: str, chunks: list[str], delay_s: float, kind="IMG"):
# 	"""
# 	Blocking send: emits per-chunk progress at DEBUG level.
# 	"""
# 	# START (optional debug log)
# 	logger.debug("[TX] start file=%s total_chunks=%d", file_label, len(chunks))
# 	start_msg = f"<START {kind}> filename: {file_label}, chunks: {len(chunks)}\n"
# 	bm.spotter_tx(start_msg.encode("ascii"))
# 	
# 	# >>> add this gap so START is observed before I0 <<<
# 	time.sleep(max(1.0, delay_s))
# 	
# 	# Per-chunk (this is the counter you want to see)
# 	total = len(chunks)
# 	for i, part in enumerate(chunks, start=1):
# 		wire = f"<I{i-1}>{part}\n".encode("ascii")
# 		bm.spotter_tx(wire)
# 		logger.debug("[TX] [%d/%d] %s", i, total, file_label)
# 		time.sleep(max(0.0, float(delay_s)))
# 	
# 	# END (optional debug log)
# 	end_msg = f"<END {kind}>\n"
# 	bm.spotter_tx(end_msg.encode("ascii"))
# 	logger.debug("[TX] done file=%s total_chunks=%d", file_label, total)
def send_chunks_to_spotter(bm, *, file_label: str, chunks: list[str],
					   delay_s: float, kind: str = "IMG"):
	n = len(chunks)
	
	# START
	start_line = f"<START {kind}> filename: {file_label}, chunks: {n}\n".encode("ascii")
	bm.spotter_tx(start_line)
	logger.info("[TX] START %s chunks=%d", file_label, n)
	
	# Give START a head-start on the queue so it precedes I0 downstream
	time.sleep(max(1.0, delay_s))
	
	# CHUNKS (log sequence at INFO; details at DEBUG)
	for i, b64 in enumerate(chunks):
		bm.spotter_tx(f"<I{i}>{b64}\n".encode("ascii"))
		logger.info("[TX] I%d/%d", i, n)  # visible at INFO & DEBUG
		if logger.isEnabledFor(logging.DEBUG):
			logger.debug("[TX] chunk=%d len(b64)=%d", i, len(b64))
		time.sleep(delay_s)
	
	# END
	bm.spotter_tx(f"<END {kind}>\n".encode("ascii"))
	logger.info("[TX] END %s", file_label)
	
	
# Added Sep 9 - testing dedupes
# --- YAML-driven TX settings (read by image handler) -------------------------
def get_spotter_tx_settings() -> dict:
	"""
	Read chunking & pacing from YAML. If keys are absent, fall back to safe defaults.
	Looks first under danger_zone.transport.spotter, then transport.spotter.
	"""
	try:
		# local import avoids any import cycle during early startup
		from bm_camera.common.config import load_config
		cfg = load_config()
	except Exception:
		cfg = {}

	dz_transport = (cfg.get("danger_zone") or {}).get("transport") or {}
	primary      = (cfg.get("transport") or {}).get("spotter") or {}
	override     = dz_transport.get("spotter") or {}

	spot = {**primary, **override}  # danger_zone overrides primary if present
	return {
		"chunk_size": int(spot.get("chunk_size", 300)),
		"delay_s":   float(spot.get("delay_s", 5.0)),
	}
