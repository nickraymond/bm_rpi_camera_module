from pathlib import Path
import os, yaml
from typing import Dict, Any

# repository root is two levels up from this file
ROOT = Path(__file__).resolve().parents[2]

CANDIDATES = [
    Path(os.environ.get("BM_AGENT_CONFIG")) if os.environ.get("BM_AGENT_CONFIG") else None,
    ROOT / "config.yaml",                           # preferred new location
    ROOT / "bm_camera" / "agent" / "config.yaml",   # old location (fallback)
]

def load_config() -> Dict[str, Any]:
    for p in CANDIDATES:
        if p and p.exists():
            with open(p, "r") as f:
                return yaml.safe_load(f) or {}
    return {}

def get_resolutions():
    cfg = load_config()
    cam = cfg.get("camera", {})
    return cam.get("resolutions", {}) or {}

def resolve_resolution(key: str):
    res = get_resolutions()
    if key not in res:
        raise ValueError("Invalid resolution key. Choose from: %s" % ", ".join(sorted(res.keys())))
    val = res[key]
    if isinstance(val, (list, tuple)) and len(val) == 2:
        return (int(val[0]), int(val[1]))
    raise ValueError(f"Resolution '{key}' has invalid format: {val!r}")

def get_camera_defaults(mode: str):
    cfg = load_config()
    cam = cfg.get("camera", {})
    d = cam.get("defaults", {}) or {}
    common = d.get("common", {}) or {}
    mode_d = d.get(mode, {}) or {}
    base = {
        "res": "720p",
        "burst": 1,
        "interval_s": 0.0,
        "dur_s": 3.0,
        "fps": 30,
        "bitrate": 3_000_000,
        "hflip": False,
        "vflip": False,
    }
    merged = {**base, **common, **mode_d}
    return merged

def get_status_topic() -> str:
    cfg = load_config()
    cam = cfg.get("camera", {})
    return cam.get("status_topic", "camera/status")

def get_spotter_tx_settings() -> dict:
    cfg = load_config()
    dz = cfg.get("danger_zone", {}) or {}
    t  = dz.get("transport", {}) or {}
    s  = t.get("spotter", {}) or {}
    return {
        "chunk_size": int(s.get("chunk_size", 300)),
        "delay_s": float(s.get("delay_s", 5.0)),
    }
