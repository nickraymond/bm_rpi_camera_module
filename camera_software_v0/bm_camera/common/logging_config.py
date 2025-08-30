# bm_camera/common/logging_config.py
from __future__ import annotations
import logging
import logging.handlers
from pathlib import Path
from typing import Any, Dict

def setup_logging(cfg: Dict[str, Any]) -> logging.Logger:
	log_cfg = (cfg or {}).get("log", {}) or {}
	level_name = str(log_cfg.get("level", "INFO")).upper()
	level = getattr(logging, level_name, logging.INFO)

	root = logging.getLogger()              # root logger
	root.setLevel(level)

	# Clear existing handlers (helpful during dev reloads)
	for h in list(root.handlers):
		root.removeHandler(h)

	fmt = logging.Formatter(
		fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
		datefmt="%Y-%m-%dT%H:%M:%S%z"
	)

	if log_cfg.get("console", True):
		ch = logging.StreamHandler()
		ch.setLevel(level)
		ch.setFormatter(fmt)
		root.addHandler(ch)

	file_path = log_cfg.get("file")
	if file_path:
		path = Path(file_path)
		path.parent.mkdir(parents=True, exist_ok=True)
		fh = logging.handlers.RotatingFileHandler(
			filename=str(path),
			maxBytes=int(log_cfg.get("max_bytes", 1_048_576)),
			backupCount=int(log_cfg.get("backups", 3)),
		)
		fh.setLevel(level)
		fh.setFormatter(fmt)
		root.addHandler(fh)

	# Return a project-scoped logger for convenience
	return logging.getLogger("bm_camera")
