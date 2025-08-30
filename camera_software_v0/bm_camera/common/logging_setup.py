# bm_camera/common/logging_setup.py
from pathlib import Path
import logging
import logging.handlers

def setup_logging(cfg: dict):
	section = (cfg or {}).get("logging", {})  # YAML: top-level 'logging'
	level_name = str(section.get("level", "INFO")).upper()
	level = getattr(logging, level_name, logging.INFO)

	log_dir = Path(section.get("dir", "/home/pi/bm_camera/logs")).expanduser()
	log_dir.mkdir(parents=True, exist_ok=True)
	log_file = log_dir / section.get("file", "bm_camera.log")

	max_bytes = int(section.get("rotate_max_bytes", 1_000_000))
	backups   = int(section.get("rotate_backups", 5))
	console   = bool(section.get("console", True))

	root = logging.getLogger()
	root.setLevel(level)

	fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

	fh = logging.handlers.RotatingFileHandler(
		log_file, maxBytes=max_bytes, backupCount=backups
	)
	fh.setFormatter(fmt)
	fh.setLevel(level)
	root.addHandler(fh)

	if console:
		ch = logging.StreamHandler()
		ch.setFormatter(fmt)
		ch.setLevel(level)
		root.addHandler(ch)

	# Quiet noisy libs unless debugging them
	logging.getLogger("picamera2").setLevel(logging.WARNING)
	logging.getLogger("libcamera").setLevel(logging.WARNING)
