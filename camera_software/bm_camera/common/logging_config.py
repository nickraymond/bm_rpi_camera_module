# # bm_camera/common/logging_config.py
# from __future__ import annotations
# import logging
# import logging.handlers
# from pathlib import Path
# from typing import Any, Dict
# 
# def setup_logging(cfg: Dict[str, Any]) -> logging.Logger:
# 	#log_cfg = (cfg or {}).get("log", {}) or {}
# 	log_cfg = cfg.get("logging", {})
# 	level_name = str(log_cfg.get("level", "INFO")).upper()
# 	level = getattr(logging, level_name, logging.INFO)
# 
# 	root = logging.getLogger()              # root logger
# 	root.setLevel(level)
# 
# 	# Clear existing handlers (helpful during dev reloads)
# 	for h in list(root.handlers):
# 		root.removeHandler(h)
# 
# 	# fmt = logging.Formatter(
# 	# 	fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
# 	# 	datefmt="%Y-%m-%dT%H:%M:%S%z"
# 	# )
# 	fmt = logging.Formatter(
# 		fmt="%(asctime)s [%(name)s] [%(levelname)s] %(message)s",
# 		datefmt="%Y-%m-%dT%H:%M:%S.%fZ"
# 	)
# 
# 	if log_cfg.get("console", True):
# 		ch = logging.StreamHandler()
# 		ch.setLevel(level)
# 		ch.setFormatter(fmt)
# 		root.addHandler(ch)
# 
# 	file_path = log_cfg.get("file")
# 	if file_path:
# 		path = Path(file_path)
# 		path.parent.mkdir(parents=True, exist_ok=True)
# 		fh = logging.handlers.RotatingFileHandler(
# 			filename=str(path),
# 			maxBytes=int(log_cfg.get("max_bytes", 1_048_576)),
# 			backupCount=int(log_cfg.get("backups", 3)),
# 		)
# 		fh.setLevel(level)
# 		fh.setFormatter(fmt)
# 		root.addHandler(fh)
# 
# 	# Return a project-scoped logger for convenience
# 	return logging.getLogger("bm_camera")
# bm_camera/common/logging_config.py
from __future__ import annotations
import logging
import logging.handlers
from pathlib import Path
from typing import Any, Dict

def _resolve_log_path(log_cfg: Dict[str, Any]) -> Path:
	"""
	Combine logging.dir + logging.file into a full path.
	If 'file' is absolute, it wins. Otherwise join 'dir'/'file'.
	"""
	file_name = str(log_cfg.get("file", "bm_camera.log")).strip()
	if not file_name:
		file_name = "bm_camera.log"

	p = Path(file_name)
	if p.is_absolute():
		return p

	dir_val = str(log_cfg.get("dir", "")).strip()
	if dir_val:
		return Path(dir_val).expanduser().resolve() / file_name

	# No dir provided: put log next to current working dir
	return Path.cwd() / file_name

def setup_logging(cfg: Dict[str, Any]) -> logging.Logger:
	log_cfg = (cfg or {}).get("logging", {}) or {}

	# Level
	level_name = str(log_cfg.get("level", "INFO")).upper()
	level = getattr(logging, level_name, logging.INFO)

	# Get root and wipe any preexisting handlers (avoid duplicates)
	root = logging.getLogger()
	root.setLevel(level)
	for h in list(root.handlers):
		root.removeHandler(h)

	# Format matches your desired style: ISO time, [LABEL] [LEVEL] prefix
	fmt = logging.Formatter(
		fmt="%(asctime)s [%(name)s] [%(levelname)s] %(message)s",
		datefmt="%Y-%m-%dT%H:%M:%S.%fZ",
	)

	# Console handler (optional, controlled by YAML)
	if bool(log_cfg.get("console", True)):
		ch = logging.StreamHandler()
		ch.setLevel(level)
		ch.setFormatter(fmt)
		root.addHandler(ch)

	# File handler (if file or dir+file provided)
	try:
		log_path = _resolve_log_path(log_cfg)
		log_path.parent.mkdir(parents=True, exist_ok=True)

		fh = logging.handlers.RotatingFileHandler(
			filename=str(log_path),
			maxBytes=int(log_cfg.get("rotate_max_bytes", 1_048_576)),
			backupCount=int(log_cfg.get("rotate_backups", 5)),
		)
		fh.setLevel(level)
		fh.setFormatter(fmt)
		root.addHandler(fh)
	except Exception as e:
		# If file logging fails, keep console logging so you see the error
		logging.getLogger("LOGGING").warning("file handler setup failed: %r", e)

	# Return a convenience logger for your app
	return logging.getLogger("AGENT")
