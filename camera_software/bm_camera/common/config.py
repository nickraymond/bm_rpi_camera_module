# # bm_camera/common/config.py
# from pathlib import Path
# import os
# 
# try:
# 	import yaml  # PyYAML
# except Exception:
# 	yaml = None
# 
# # camera_software root (…/camera_software)
# ROOT = Path(__file__).resolve().parents[2]
# DEFAULT_CFG = ROOT / "bm_agent" / "config.yaml"
# 
# def load_config():
# 	"""Load bm_agent/config.yaml (or BM_AGENT_CONFIG if set)."""
# 	path = Path(os.environ.get("BM_AGENT_CONFIG") or DEFAULT_CFG)
# 	if yaml is None:
# 		return {}
# 	try:
# 		with open(path, "r") as f:
# 			return yaml.safe_load(f) or {}
# 	except Exception:
# 		return {}
# 
# def get_resolutions():
# 	"""Return dict like {'720p': (1280,720), ...} from YAML (normalized), else {}."""
# 	cfg = load_config()
# 	cam = cfg.get("camera", {})
# 	res = cam.get("resolutions", {}) or {}
# 	out = {}
# 	for k, v in res.items():
# 		if isinstance(v, (list, tuple)) and len(v) == 2:
# 			try:
# 				out[k] = (int(v[0]), int(v[1]))
# 			except Exception:
# 				pass
# 	return out
# 
# def get_camera_defaults(mode: str) -> dict:
# 		cfg = load_config()
# 		cam = cfg.get("camera", {})
# 		d = cam.get("defaults", {}) or {}
# 		common = d.get("common", {}) or {}
# 		mode_d = d.get(mode, {}) or {}
# 	
# 		# a safe superset for both modes; mode code will only use what it needs
# 		base = {
# 			"res": "720p",
# 			"burst": 1,
# 			"interval_s": 0.0,
# 			"dur_s": 3.0,
# 			"fps": 30,
# 			"bitrate": 3_000_000,
# 			"hflip": False,
# 			"vflip": False,
# 		}
# 		merged = {**base, **common, **mode_d}
# 		return merged
# 
# def get_status_topic() -> str:
# 	cfg = load_config()
# 	cam = cfg.get("camera", {})
# 	return cam.get("status_topic", "camera/status")
# 
# def resolve_resolution(key: str):
# 	"""Return (width, height) from YAML or raise a helpful error."""
# 	res = get_resolutions()
# 	if key not in res:
# 		raise ValueError("Invalid resolution key. Choose from: %s" % ", ".join(sorted(res.keys())))
# 	wh = res[key]
# 	# Ensure tuple[int,int]
# 	return (int(wh[0]), int(wh[1]))
from pathlib import Path
from typing import Dict, Tuple, Any
import yaml

# Project root: .../camera_software
ROOT = Path(__file__).resolve().parents[2]
CFG_PATH = ROOT / "bm_agent" / "config.yaml"

def load_config() -> Dict[str, Any]:
	if not CFG_PATH.exists():
		return {}
	with open(CFG_PATH, "r") as f:
		data = yaml.safe_load(f) or {}
	return data

def get_resolutions() -> Dict[str, Tuple[int, int]]:
	cfg = load_config()
	cam = cfg.get("camera", {})
	res = cam.get("resolutions", {}) or {}
	out: Dict[str, Tuple[int, int]] = {}
	for k, v in res.items():
		if isinstance(v, (list, tuple)) and len(v) == 2:
			out[str(k)] = (int(v[0]), int(v[1]))
	return out

def resolve_resolution(key: str) -> Tuple[int, int]:
	res = get_resolutions()
	if key not in res:
		raise ValueError("Invalid resolution key. Choose from: %s" % ", ".join(sorted(res.keys())))
	return res[key]

def get_camera_defaults(mode: str) -> Dict[str, Any]:
	"""
	mode: "image" or "video"
	Merge base -> common -> mode-specific defaults.
	"""
	cfg = load_config()
	cam = cfg.get("camera", {})
	d = cam.get("defaults", {}) or {}
	common = d.get("common", {}) or {}
	mode_d = d.get(mode, {}) or {}

	base = {
		"res": "720p",
		# image
		"burst": 1,
		"interval_s": 0.0,
		# video
		"dur_s": 3.0,
		"fps": 30,
		"bitrate": 3_000_000,
		"hflip": False,
		"vflip": False,
	}
	merged: Dict[str, Any] = {**base, **common, **mode_d}
	return merged

def get_status_topic() -> str:
	cfg = load_config()
	cam = cfg.get("camera", {})
	return cam.get("status_topic", "camera/status")
