# # # filename: bm_camera/camera_software/bm_agent/handlers/capture_video_cmd.py

import os, sys
from pathlib import Path

from camera_lock import CameraLock
from .status_util import ack_print # <<<< obsolete from spotter_log
from bm_agent.handlers.spotter_log import spotter_log


# make camera_software visible on sys.path
CAMERA_SW_DIR = Path(__file__).resolve().parents[3]
sp = str(CAMERA_SW_DIR)
if sp not in sys.path:
    sys.path.insert(0, sp)

from video_capture import save_video  # capture module decides directory

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

    cam     = ctx.get("cfg", {}).get("camera", {})
    vid_def = cam.get("defaults", {}).get("video", {})

    res   = p.get("res",  vid_def.get("res", "720p"))
    dur   = _parse_seconds(p.get("dur", f'{vid_def.get("dur_s", 3.0)}s'))
    fps   = int(p.get("fps", vid_def.get("fps", 30)))
    br    = _parse_num_with_units(p.get("br",  str(vid_def.get("bitrate", 3_000_000))))
    hflip = str(p.get("hflip", str(vid_def.get("hflip", False)))).lower() in ("1","true","yes")
    vflip = str(p.get("vflip", str(vid_def.get("vflip", False)))).lower() in ("1","true","yes")

    # lock long enough for the whole clip + margin
    lock_timeout = max(10.0, float(dur) + 5.0)
    try:
        with CameraLock(timeout_s=lock_timeout):
            path = save_video(
                base_name="VID",
                duration_s=dur,
                resolution_key=res,
                fps=fps,
                bitrate=br,
                hflip=hflip,
                vflip=vflip,
            )
#         size = os.path.getsize(path) if os.path.exists(path) else -1
#         print(f"[CAM/VID] SAVED {path} ({size} bytes) res={res} dur={dur}s fps={fps} br={br}")
# 
#         fn = os.path.basename(path)
#         ack_print(ctx, f"OK video file={fn} res={res} dur={dur}s fps={fps} br={br} bytes={size}")
        size = os.path.getsize(path) if os.path.exists(path) else -1
        print(f"[CAM/VID] SAVED {path} ({size} bytes) res={res} dur={dur}s fps={fps} br={br}")
        
        # Spotter-friendly line
        from pathlib import Path as _P
        spotter_log(ctx,
                    level="INFO", tag="CAM", msg="video saved",
                    file=_P(path).name, res=res, dur=dur, fps=fps, br=br, size=size)

    except TimeoutError:
        print("[CAM/VID][BUSY] camera in use; drop trigger")
        spotter_log(ctx, level="ERR", tag="CAM", msg="video failed", reason="busy")
    except Exception as e:
        print(f"[CAM/VID][ERR] {e!r}")
        spotter_log(ctx, level="ERR", tag="CAM", msg="video failed", reason=type(e).__name__)                    