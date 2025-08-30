# # # # filename: bm_camera/camera_software/bm_agent/handlers/capture_video_cmd.py
import logging
import os, sys
from pathlib import Path
from bm_camera.utils.camera_lock import CameraLock
from bm_camera.capture import capture_video

logger = logging.getLogger("bm_camera.video")

# make camera_software visible on sys.path
CAMERA_SW_DIR = Path(__file__).resolve().parents[3]
sp = str(CAMERA_SW_DIR)
if sp not in sys.path:
    sys.path.insert(0, sp)

from bm_camera.common.config import get_camera_defaults
from .status_util import send_status

def _payload_to_str(data: bytes) -> str:
    if not data:
        return ""
    body = data[1:] if data and data[0] < 0x20 else data
    s = body.decode("utf-8", "ignore").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1]
    return s

def _parse_tokens(s: str) -> dict:
    if s in ("", "1", "go", "trigger"):
        return {}
    if "=" not in s and "," not in s:
        return {"res": s}
    out = {}
    for tok in s.split(","):
        if not tok:
            continue
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k.strip()] = v.strip()
    return out

def _parse_num_with_units(val: str) -> int:
    v = val.lower()
    if v.endswith("m"):
        return int(float(v[:-1]) * 1_000_000)
    if v.endswith("k"):
        return int(float(v[:-1]) * 1_000)
    return int(v)

def _parse_seconds(val: str) -> float:
    v = val.lower()
    if v.endswith("ms"):
        return float(v[:-2]) / 1000.0
    if v.endswith("s"):
        return float(v[:-1])
    return float(v)

def init(ctx):
    pass

def cleanup(ctx):
    pass

def handle(node_id, topic: str, data: bytes, ctx):
    p = _parse_tokens(_payload_to_str(data))
    defaults = get_camera_defaults("video")

    res   = p.get("res", defaults["res"])
    dur   = _parse_seconds(p.get("dur", f'{defaults["dur_s"]}s'))
    fps   = int(p.get("fps", defaults["fps"]))
    br    = _parse_num_with_units(p.get("br", str(defaults["bitrate"])))
    hflip = str(p.get("hflip", str(defaults["hflip"]))).lower() in ("1","true","yes")
    vflip = str(p.get("vflip", str(defaults["vflip"]))).lower() in ("1","true","yes")

    lock_timeout = max(10.0, float(dur) + 5.0)
    try:
        with CameraLock(timeout_s=lock_timeout):
            path = capture_video(
                base_name="VID",
                duration_s=dur,
                resolution_key=res,
                fps=fps,
                bitrate=br,
                hflip=hflip,
                vflip=vflip,
            )
        size = os.path.getsize(path) if os.path.exists(path) else -1
        # print(f"[CAM/VID] SAVED {path} ({size} bytes) res={res} dur={dur}s fps={fps} br={br}")
        logger.info("[CAM/VID] SAVED %s (%d bytes) res=%s dur=%ss fps=%d br=%d",
        path, size, res, dur, fps, br)
        send_status(ctx, "OK", op="video", file=os.path.basename(path), res=res, dur=f"{dur}s", fps=fps, br=br, bytes=size)
    except TimeoutError:
        # print("[CAM/VID][BUSY] camera in use; drop trigger")
        logger.warning("[CAM/VID][BUSY] camera in use; drop trigger")
        send_status(ctx, "BUSY", op="video")
    except Exception as e:
        # print(f"[CAM/VID][ERR] {e!r}")
        logger.exception("[CAM/VID][ERR] %r", e)
        send_status(ctx, "ERR", op="video", reason=type(e).__name__)
