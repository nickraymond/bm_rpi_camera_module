# bm_camera/common/logging_setup.py
import logging, time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timezone

# Map dotted logger names to short bracket tags
_TAGS = {
	"bm_camera.agent": "AGENT",
	"bm_camera.bus": "BUS",
	"bm_camera.image": "IMG",
	"bm_camera.video": "VID",
	"bm_camera.tx.spotter": "TX",
	"bm_camera.clock": "CLOCK",
	"bm_camera.rtc": "RTC",
}

fmt = "%(asctime)sZ [%(name)s] [%(levelname)s] %(message)s"
datefmt = "%Y-%m-%dT%H:%M:%S"

formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
formatter.converter = time.gmtime  # force UTC so %Z becomes Z

class SpotterStyleFormatter(logging.Formatter):
	# We’ll compute ISO-8601 UTC with milliseconds and Z suffix
	def formatTime(self, record, datefmt=None):
		dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
		# match 3-digit milliseconds like the Spotter examples
		return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(dt.microsecond/1000):03d}Z"

	def format(self, record):
		# Inject a short tag based on logger name
		name = record.name
		record.tag = _TAGS.get(name, name.split(".")[-1].upper())
		# Final line: 2025-08-29T23:20:25.886Z [TAG] [LEVEL] message
		record.asctime = self.formatTime(record)
		return f"{record.asctime} [{record.tag}] [{record.levelname}] {record.getMessage()}"

def setup_logging(cfg: dict):
	# YAML: logging.level and logging.file are optional
	log_cfg = (cfg or {}).get("logging", {}) or {}
	level_str = str(log_cfg.get("level", "INFO")).upper()
	level = getattr(logging, level_str, logging.INFO)

	# Console handler
	ch = logging.StreamHandler()
	ch.setLevel(level)
	ch.setFormatter(SpotterStyleFormatter())

	# File handler (rotate, ~1MB x 5)
	log_dir = Path((cfg.get("paths", {}) or {}).get("data_root", Path.cwd()))
	out_file = log_cfg.get("file", str(log_dir / "logs" / "bm_camera.log"))
	Path(out_file).parent.mkdir(parents=True, exist_ok=True)
	fh = RotatingFileHandler(out_file, maxBytes=1_000_000, backupCount=5)
	fh.setLevel(level)
	fh.setFormatter(SpotterStyleFormatter())

	# Root config
	root = logging.getLogger()
	root.handlers[:] = []
	root.setLevel(level)
	root.addHandler(ch)
	root.addHandler(fh)

	# Set useful child loggers (names drive the [TAG] mapping)
	logging.getLogger("bm_camera.agent").setLevel(level)
	logging.getLogger("bm_camera.bus").setLevel(level)
	logging.getLogger("bm_camera.image").setLevel(level)
	logging.getLogger("bm_camera.video").setLevel(level)
	logging.getLogger("bm_camera.tx.spotter").setLevel(level)
	logging.getLogger("bm_camera.clock").setLevel(level)
	logging.getLogger("bm_camera.rtc").setLevel(level)
