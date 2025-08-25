import os
from pathlib import Path
import yaml

def _default_base() -> Path:
    # camera_software/
    return Path(__file__).resolve().parents[2]

def _load_cfg() -> dict:
    # 1) env override
    cfg_path = os.environ.get("BM_AGENT_CONFIG")
    if cfg_path and Path(cfg_path).exists():
        try:
            with open(cfg_path, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
    # 2) default agent config
    candidate = _default_base() / "bm_agent" / "config.yaml"
    if candidate.exists():
        try:
            with open(candidate, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
    return {}

_cfg = _load_cfg()

def data_root() -> Path:
    root = (_cfg.get("paths", {}) or {}).get("data_root")
    if root:
        p = Path(os.path.expanduser(root))
    else:
        p = _default_base()
    return p

def _ensure(subkey: str, default_subdir: str) -> str:
    sub = (_cfg.get("paths", {}) or {}).get(subkey, default_subdir)
    p = data_root() / sub
    p.mkdir(parents=True, exist_ok=True)
    return str(p)

def image_dir() -> str:
    return _ensure("images", "images")

def video_dir() -> str:
    return _ensure("videos", "videos")

def buffer_dir() -> str:
    return _ensure("buffer", "buffer")
