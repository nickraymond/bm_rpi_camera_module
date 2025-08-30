# 
# # bm_camera/common/config.py
# from pathlib import Path
# from typing import Dict, Tuple, Any
# import os
# import yaml
# 
# # Paths:
# #   <pkg>/common/config.py  -> parents[1] = <pkg> = .../bm_camera
# #   new default config      -> <pkg>/agent/config.yaml
# #   legacy fallback         -> .../camera_software/bm_agent/config.yaml
# _PKG_ROOT = Path(__file__).resolve().parents[1]
# _NEW_DEFAULT = _PKG_ROOT / "agent" / "config.yaml"
# _LEGACY_DEFAULT = Path(__file__).resolve().parents[2] / "bm_agent" / "config.yaml"
# 
# def _first_existing(paths):
# 	for p in paths:
# 		if p and Path(p).exists():
# 			return Path(p)
# 	return None
# 
# def resolve_config_path(path: str = None) -> Path:
# 	"""
# 	Decide which config.yaml to use:
# 	  1) explicit 'path' arg
# 	  2) BM_AGENT_CONFIG env var
# 	  3) new default:  <pkg>/agent/config.yaml
# 	  4) legacy:       ../bm_agent/config.yaml
# 	"""
# 	candidates = []
# 	if path:
# 		candidates.append(path)
# 	env = os.environ.get("BM_AGENT_CONFIG")
# 	if env:
# 		candidates.append(env)
# 	candidates += [_NEW_DEFAULT, _LEGACY_DEFAULT]
# 	p = _first_existing(candidates)
# 	return p
# 
# def load_config(path: str = None) -> Dict[str, Any]:
# 	p = resolve_config_path(path)
# 	if not p:
# 		return {}
# 	with open(p, "r") as f:
# 		return yaml.safe_load(f) or {}
# 
# def get_resolutions() -> Dict[str, Tuple[int, int]]:
# 	cfg = load_config()
# 	cam = cfg.get("camera", {})
# 	res = cam.get("resolutions", {}) or {}
# 	out: Dict[str, Tuple[int, int]] = {}
# 	for k, v in res.items():
# 		if isinstance(v, (list, tuple)) and len(v) == 2:
# 			out[str(k)] = (int(v[0]), int(v[1]))
# 	return out
# 
# def resolve_resolution(key: str) -> Tuple[int, int]:
# 	res = get_resolutions()
# 	if key not in res:
# 		raise ValueError("Invalid resolution key. Choose from: %s" % ", ".join(sorted(res.keys())))
# 	return res[key]
# 
# def get_camera_defaults(mode: str) -> Dict[str, Any]:
# 	"""
# 	Merge base -> common -> mode-specific defaults.
# 	mode: "image" or "video"
# 	"""
# 	cfg = load_config()
# 	cam = cfg.get("camera", {})
# 	d = cam.get("defaults", {}) or {}
# 	common = d.get("common", {}) or {}
# 	mode_d = d.get(mode, {}) or {}
# 
# 	base = {
# 		"res": "720p",
# 		# image
# 		"burst": 1,
# 		"interval_s": 0.0,
# 		# video
# 		"dur_s": 3.0,
# 		"fps": 30,
# 		"bitrate": 3_000_000,
# 		"hflip": False,
# 		"vflip": False,
# 	}
# 	return {**base, **common, **mode_d}
# 
# def get_status_topic() -> str:
# 	cfg = load_config()
# 	# Prefer topics map if present, otherwise camera.status_topic, else default.
# 	topics = cfg.get("topics", {}) or {}
# 	if "camera_status" in topics:
# 		return topics["camera_status"]
# 	cam = cfg.get("camera", {}) or {}
# 	return cam.get("status_topic", "camera/status")
# bm_camera/common/config.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Tuple, Any
import yaml

# Project root is .../camera_software
ROOT = Path(__file__).resolve().parents[2]
# New location of config.yaml (under the agent package)
CFG_PATH = ROOT / "bm_camera" / "agent" / "config.yaml"

def load_config() -> Dict[str, Any]:
	"""Load YAML config (returns {} if missing)."""
	if not CFG_PATH.exists():
		return {}
	with open(CFG_PATH, "r") as f:
		data = yaml.safe_load(f) or {}
	return data

# ---------- Paths / Topics / UART ----------
def get_uart_settings() -> Tuple[str, int]:
	cfg = load_config()
	return (
		cfg.get("uart_device", "/dev/serial0"),
		int(cfg.get("baudrate", 115200)),
	)

def get_topics() -> Dict[str, str]:
	"""Return topics mapping exactly as in YAML (may be {})."""
	cfg = load_config()
	return cfg.get("topics", {}) or {}

def get_status_topic() -> str:
	"""
	Prefer an explicit status topic in topics:, else camera/status.
	"""
	return get_topics().get("camera_status", "camera/status")

# ---------- Resolutions ----------
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

# ---------- Camera defaults ----------
_BASE_DEFAULTS: Dict[str, Any] = {
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

def get_camera_defaults(mode: str) -> Dict[str, Any]:
	"""
	mode: "image" or "video"
	Merge base -> camera.defaults.common -> camera.defaults.<mode>.
	"""
	cfg = load_config()
	cam = cfg.get("camera", {})
	d = cam.get("defaults", {}) or {}
	common = d.get("common", {}) or {}
	mode_d = d.get(mode, {}) or {}
	merged = {**_BASE_DEFAULTS, **common, **mode_d}

	# If YAML asked for a res that doesn't exist, fall back to a valid one
	try:
		resolve_resolution(merged["res"])
	except Exception:
		# if user’s value is bad, pick a safe fallback (first available)
		res_map = get_resolutions()
		if res_map:
			merged["res"] = next(iter(res_map.keys()))
		else:
			merged["res"] = "720p"
	return merged
