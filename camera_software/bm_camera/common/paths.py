# # camera_software/common/paths.py
# import os
# import yaml
# from pathlib import Path
# 
# def _default_base():
# 	# project-root/camera_software
# 	return Path(__file__).resolve().parents[1]
# 
# def _load_cfg():
# 	# 1) env override
# 	cfg_path = os.environ.get("BM_AGENT_CONFIG")
# 	if cfg_path and Path(cfg_path).exists():
# 		with open(cfg_path, "r") as f:
# 			return yaml.safe_load(f) or {}
# 	# 2) default alongside agent
# 	candidate = _default_base() / "bm_agent" / "config.yaml"
# 	if candidate.exists():
# 		with open(candidate, "r") as f:
# 			return yaml.safe_load(f) or {}
# 	return {}
# 
# _cfg = _load_cfg()
# 
# def data_root():
# 	# config.paths.data_root OR camera_software/
# 	root = (_cfg.get("paths", {}) or {}).get("data_root")
# 	if root:
# 		p = Path(os.path.expanduser(root))
# 	else:
# 		p = _default_base()
# 	return p
# 
# def image_dir():
# 	sub = (_cfg.get("paths", {}) or {}).get("images", "images")
# 	p = data_root() / sub
# 	p.mkdir(parents=True, exist_ok=True)
# 	return str(p)
# 
# def video_dir():
# 	sub = (_cfg.get("paths", {}) or {}).get("videos", "videos")
# 	p = data_root() / sub
# 	p.mkdir(parents=True, exist_ok=True)
# 	return str(p)
# 
# def buffer_dir():
# 	sub = (_cfg.get("paths", {}) or {}).get("buffer", "buffer")
# 	p = data_root() / sub
# 	p.mkdir(parents=True, exist_ok=True)
# 	return str(p)


# bm_camera/common/paths.py
from __future__ import annotations
from pathlib import Path
from typing import Optional
from bm_camera.common.config import load_config

def _data_root() -> Path:
	"""
	Resolve the writable root for outputs.
	Priority:
	  1) YAML: paths.data_root
	  2) Project root (one level above bm_camera package)
	"""
	cfg = load_config() or {}
	p = (cfg.get("paths") or {}).get("data_root")
	if p:
		return Path(p).expanduser()
	# default: .../camera_software (one level above bm_camera/)
	return Path(__file__).resolve().parents[2]

def _ensure(path: Path) -> Path:
	path.mkdir(parents=True, exist_ok=True)
	return path

def image_dir() -> str:
	cfg = load_config() or {}
	sub = (cfg.get("paths") or {}).get("images", "images")
	return str(_ensure(_data_root() / sub))

def video_dir() -> str:
	cfg = load_config() or {}
	sub = (cfg.get("paths") or {}).get("videos", "videos")
	return str(_ensure(_data_root() / sub))

def buffer_dir() -> str:
	cfg = load_config() or {}
	sub = (cfg.get("paths") or {}).get("buffer", "buffer")
	return str(_ensure(_data_root() / sub))
