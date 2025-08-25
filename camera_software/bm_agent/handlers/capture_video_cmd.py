
# text-only handler for topic 'camera/capture/video'
# Supports: '1' (defaults) or CSV key=val (no spaces): dur=3s,res=720p,fps=25,br=2M
import os, sys
from pathlib import Path
from camera_lock import CameraLock

# make camera_software visible on sys.path
CAMERA_SW_DIR = Path(__file__).resolve().parents[3]
sp = str(CAMERA_SW_DIR)
if sp not in sys.path:
    sys.path.insert(0, sp)

from video_capture import save_video, VIDEO_DIRECTORY

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
    try:
        os.makedirs(VIDEO_DIRECTORY, exist_ok=True)
    except Exception:
        pass

def cleanup(ctx):
    pass

def handle(node_id, topic: str, data: bytes, ctx):
    p = _parse_tokens(_payload_to_str(data))
    res = p.get("res", "720p")
    dur = _parse_seconds(p.get("dur", "3s"))
    fps = int(p.get("fps", 30))
    br  = _parse_num_with_units(p.get("br", "3M"))
    hflip = str(p.get("hflip", "0")).lower() in ("1","true","yes")
    vflip = str(p.get("vflip", "0")).lower() in ("1","true","yes")
    
    # Lock long enough for the whole clip + a little headroom
    lock_timeout = max(10.0, float(dur) + 5.0)
    
    try:
        with CameraLock(timeout_s=lock_timeout):
            path = save_video(
                base_name="VID",
                duration_s=dur,
                resolution_key=res,
                directory_path=VIDEO_DIRECTORY,
                fps=fps,
                bitrate=br,
                hflip=hflip,
                vflip=vflip,
            )
        size = os.path.getsize(path) if os.path.exists(path) else -1
        print(f"[CAM/VID] SAVED {path} ({size} bytes) res={res} dur={dur}s fps={fps} br={br}")
    except TimeoutError:
        print("[CAM/VID][BUSY] camera in use; drop trigger")
    except Exception as e:
        print(f"[CAM/VID][ERR] {e!r}")
