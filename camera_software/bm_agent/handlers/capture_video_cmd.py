# # # filename: bm_camera/camera_software/bm_agent/handlers/capture_video_cmd.py
# 
# import os, sys
# from pathlib import Path
# from camera_lock import CameraLock
# from bm_camera.common.config import get_camera_defaults
# from bm_agent.handlers.status_util import send_status
# from .status_util import ack_print
# 
# 
# 
# # make camera_software visible on sys.path
# CAMERA_SW_DIR = Path(__file__).resolve().parents[3]
# sp = str(CAMERA_SW_DIR)
# if sp not in sys.path:
#     sys.path.insert(0, sp)
# 
# from video_capture import save_video
# 
# def _payload_to_str(data: bytes) -> str:
#     if not data:
#         return ""
#     body = data[1:] if data and data[0] < 0x20 else data
#     s = body.decode("utf-8", "ignore").strip()
#     if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
#         s = s[1:-1]
#     return s
# 
# def _parse_tokens(s: str) -> dict:
#     if s in ("", "1", "go", "trigger"):
#         return {}
#     if "=" not in s and "," not in s:
#         return {"res": s}
#     out = {}
#     for tok in s.split(","):
#         if not tok:
#             continue
#         if "=" in tok:
#             k, v = tok.split("=", 1)
#             out[k.strip()] = v.strip()
#     return out
# 
# def _parse_num_with_units(val: str) -> int:
#     v = val.lower()
#     if v.endswith("m"):
#         return int(float(v[:-1]) * 1_000_000)
#     if v.endswith("k"):
#         return int(float(v[:-1]) * 1_000)
#     return int(v)
# 
# def _parse_seconds(val: str) -> float:
#     v = val.lower()
#     if v.endswith("ms"):
#         return float(v[:-2]) / 1000.0
#     if v.endswith("s"):
#         return float(v[:-1])
#     return float(v)
# 
# def _videos_dir_from_cfg(cfg: dict) -> str:
#     paths = cfg.get("paths", {})
#     root  = Path(paths.get("data_root", CAMERA_SW_DIR))
#     return str(root / paths.get("videos", "videos"))
# 
# def init(ctx):
#     os.makedirs(_videos_dir_from_cfg(ctx.get("cfg", {})), exist_ok=True)
# 
# def cleanup(ctx):
#     pass
# 
# # def handle(node_id, topic: str, data: bytes, ctx):
# #     p = _parse_tokens(_payload_to_str(data))
# #     defaults = get_camera_defaults("video")
# # 
# #     res   = p.get("res", defaults.get("res", "720p"))
# #     dur   = _parse_seconds(p.get("dur", f'{defaults.get("dur_s", 3.0)}s'))
# #     fps   = int(p.get("fps", defaults.get("fps", 30)))
# #     br    = _parse_num_with_units(p.get("br", str(defaults.get("bitrate", 3_000_000))))
# #     hflip = str(p.get("hflip", str(defaults.get("hflip", False)))).lower() in ("1","true","yes")
# #     vflip = str(p.get("vflip", str(defaults.get("vflip", False)))).lower() in ("1","true","yes")
# # 
# #     vid_dir = _videos_dir_from_cfg(ctx.get("cfg", {}))
# # 
# #     lock_timeout = max(10.0, float(dur) + 5.0)
# #     try:
# #         with CameraLock(timeout_s=lock_timeout):
# #             path = save_video(
# #                 base_name="VID",
# #                 duration_s=dur,
# #                 resolution_key=res,
# #                 directory_path=vid_dir,
# #                 fps=fps,
# #                 bitrate=br,
# #                 hflip=hflip,
# #                 vflip=vflip,
# #             )
# #         size = os.path.getsize(path) if os.path.exists(path) else -1
# #         print(f"[CAM/VID] SAVED {path} ({size} bytes) res={res} dur={dur}s fps={fps} br={br}")
# #         # send status:
# #         send_status(ctx, "OK", op="video", file=Path(path).name, res=res, dur=dur, fps=fps, br=br, bytes=size)
# # 
# #     except TimeoutError:
# #         print("[CAM/VID][BUSY] camera in use; drop trigger")
# #         send_status(ctx, "BUSY", op="video")
# #     except Exception as e:
# #         print(f"[CAM/VID][ERR] {e!r}")
# #         send_status(ctx, "ERR", op="video", reason=str(e))
# 
# def handle(node_id, topic: str, data: bytes, ctx):
#     p = _parse_tokens(_payload_to_str(data))
#     # ... your existing parse + defaults ...
#     try:
#         with CameraLock(timeout_s=max(10.0, float(dur) + 5.0)):
#             path = save_video(
#                 base_name="VID",
#                 duration_s=dur,
#                 resolution_key=res,
#                 directory_path=vid_dir,
#                 fps=fps,
#                 bitrate=br,
#                 hflip=hflip,
#                 vflip=vflip,
#             )
#         size = os.path.getsize(path) if os.path.exists(path) else -1
#         print(f"[CAM/VID] SAVED {path} ({size} bytes) res={res} dur={dur}s fps={fps} br={br}")
#     
#         # Spotter console ACK
#         fn = os.path.basename(path)
#         ack_print(ctx, f"OK video file={fn} res={res} dur={dur}s fps={fps} br={br} bytes={size}")
#     except TimeoutError:
#         print("[CAM/VID][BUSY] camera in use; drop trigger")
#         ack_print(ctx, "ERR video reason=busy")
#     except Exception as e:
#         print(f"[CAM/VID][ERR] {e!r}")
#         ack_print(ctx, f"ERR video reason={type(e).__name__}")# text-only handler for topic 'camera/capture/video'
import os, sys
from pathlib import Path

from camera_lock import CameraLock
from .status_util import ack_print

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
        size = os.path.getsize(path) if os.path.exists(path) else -1
        print(f"[CAM/VID] SAVED {path} ({size} bytes) res={res} dur={dur}s fps={fps} br={br}")

        fn = os.path.basename(path)
        ack_print(ctx, f"OK video file={fn} res={res} dur={dur}s fps={fps} br={br} bytes={size}")

    except TimeoutError:
        print("[CAM/VID][BUSY] camera in use; drop trigger")
        ack_print(ctx, "ERR video reason=busy")
    except Exception as e:
        print(f"[CAM/VID][ERR] {e!r}")
        ack_print(ctx, f"ERR video reason={type(e).__name__}")
