# camera_software/common/paths.py
import os
import yaml
from pathlib import Path

def _default_base():
	# project-root/camera_software
	return Path(__file__).resolve().parents[1]

def _load_cfg():
	# 1) env override
	cfg_path = os.environ.get("BM_AGENT_CONFIG")
	if cfg_path and Path(cfg_path).exists():
		with open(cfg_path, "r") as f:
			return yaml.safe_load(f) or {}
	# 2) default alongside agent
	candidate = _default_base() / "bm_agent" / "config.yaml"
	if candidate.exists():
		with open(candidate, "r") as f:
			return yaml.safe_load(f) or {}
	return {}

_cfg = _load_cfg()

def data_root():
	# config.paths.data_root OR camera_software/
	root = (_cfg.get("paths", {}) or {}).get("data_root")
	if root:
		p = Path(os.path.expanduser(root))
	else:
		p = _default_base()
	return p

def image_dir():
	sub = (_cfg.get("paths", {}) or {}).get("images", "images")
	p = data_root() / sub
	p.mkdir(parents=True, exist_ok=True)
	return str(p)

def video_dir():
	sub = (_cfg.get("paths", {}) or {}).get("videos", "videos")
	p = data_root() / sub
	p.mkdir(parents=True, exist_ok=True)
	return str(p)

def buffer_dir():
	sub = (_cfg.get("paths", {}) or {}).get("buffer", "buffer")
	p = data_root() / sub
	p.mkdir(parents=True, exist_ok=True)
	return str(p)
