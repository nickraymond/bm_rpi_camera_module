# # # filename: bm_camera/camera_software/bm_agent/handlers/capture_image_cmd.py
# 
# import os, sys, time
# from pathlib import Path
# from camera_lock import CameraLock
# from bm_camera.common.config import get_camera_defaults
# from bm_agent.handlers.status_util import send_status
# from .status_util import ack_print
# 
# # make camera_software visible on sys.path
# CAMERA_SW_DIR = Path(__file__).resolve().parents[3]
# sp = str(CAMERA_SW_DIR)
# if sp not in sys.path:
#     sys.path.insert(0, sp)
# 
# from image_capture import capture_image  # uses YAML-driven resolutions
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
# def _parse_ms(val: str) -> float:
#     v = val.lower()
#     if v.endswith("ms"):
#         return float(v[:-2]) / 1000.0
#     if v.endswith("s"):
#         return float(v[:-1])
#     return float(v)
# 
# def _images_dir_from_cfg(cfg: dict) -> str:
#     paths = cfg.get("paths", {})
#     root  = Path(paths.get("data_root", CAMERA_SW_DIR))
#     return str(root / paths.get("images", "images"))
# 
# def init(ctx):
#     os.makedirs(_images_dir_from_cfg(ctx.get("cfg", {})), exist_ok=True)
# 
# def cleanup(ctx):
#     pass
# 
# # def handle(node_id, topic: str, data: bytes, ctx):
# #     params = _parse_tokens(_payload_to_str(data))
# #     defaults = get_camera_defaults("image")
# # 
# #     res        = params.get("res", defaults.get("res", "1080p"))
# #     burst      = max(1, int(params.get("burst", defaults.get("burst", 1))))
# #     interval_s = _parse_ms(params.get("int", str(defaults.get("interval_s", 0.0))))
# # 
# #     img_dir = _images_dir_from_cfg(ctx.get("cfg", {}))
# # 
# #     try:
# #         # Short lock is enough for warmup + single/burst stills
# #         with CameraLock(timeout_s=max(8.0, burst * (interval_s + 1.0))):
# #             for i in range(burst):
# #                 path = capture_image(resolution_key=res, directory_path=img_dir)
# #                 size = os.path.getsize(path) if os.path.exists(path) else -1
# #                 print(f"[CAM/IMG] SAVED {path} ({size} bytes) res={res} burst={i+1}/{burst}")
# #                 send_status(ctx, "OK", op="image", file=Path(path).name, res=res, idx=i+1, burst=burst, bytes=size)
# # 
# #                 if i + 1 < burst and interval_s > 0:
# #                     time.sleep(interval_s)
# #     except TimeoutError:
# #         print("[CAM/IMG][BUSY] camera in use; drop trigger")
# #         send_status(ctx, "BUSY", op="image")
# #     except Exception as e:
# #         print(f"[CAM/IMG][ERR] {e!r}")
# #         send_status(ctx, "ERR", op="image", reason=str(e))
# def handle(node_id, topic: str, data: bytes, ctx):
#     params = _parse_tokens(_payload_to_str(data))
#     # ... your existing parse code ...
#     try:
#         with CameraLock(timeout_s=8.0):
#             for i in range(burst):
#                 path = capture_image(resolution_key=res, directory_path=IMAGE_DIRECTORY)
#                 size = os.path.getsize(path) if os.path.exists(path) else -1
#                 print(f"[CAM/IMG] SAVED {path} ({size} bytes) res={res} burst={i+1}/{burst}")
#     
#                 # Spotter console ACK (short and greppable)
#                 fn = os.path.basename(path)
#                 ack_print(ctx, f"OK image file={fn} res={res} bytes={size} idx={i+1}/{burst}")
#     
#                 if i + 1 < burst and interval_s > 0:
#                     time.sleep(interval_s)
#     except TimeoutError:
#         print("[CAM/IMG][BUSY] camera in use; drop trigger")
#         ack_print(ctx, "ERR image reason=busy")
#     except Exception as e:
#         print(f"[CAM/IMG][ERR] {e!r}")
#         ack_print(ctx, f"ERR image reason={type(e).__name__}")  
# text-only handler for topic 'camera/capture/image'
import os, sys, time
from pathlib import Path

from camera_lock import CameraLock
from .status_util import ack_print

# make camera_software visible on sys.path
CAMERA_SW_DIR = Path(__file__).resolve().parents[3]
sp = str(CAMERA_SW_DIR)
if sp not in sys.path:
    sys.path.insert(0, sp)

# prefer image_capture; fall back to process_image for legacy
try:
    from image_capture import capture_image
except ImportError:
    from process_image import capture_image

# ---------- helpers ----------
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

def _parse_ms(val: str) -> float:
    v = val.lower()
    if v.endswith("ms"):
        return float(v[:-2]) / 1000.0
    if v.endswith("s"):
        return float(v[:-1])
    return float(v)

def init(ctx):  # no-op; image dir is resolved by capture_image
    pass

def cleanup(ctx):
    pass

def handle(node_id, topic: str, data: bytes, ctx):
    # parse payload
    params = _parse_tokens(_payload_to_str(data))

    # pull defaults from YAML
    cam = ctx.get("cfg", {}).get("camera", {})
    img_def = cam.get("defaults", {}).get("image", {})

    res        = params.get("res", img_def.get("res", "1080p"))
    burst      = max(1, int(params.get("burst", img_def.get("burst", 1))))
    interval_s = _parse_ms(params.get("int", str(img_def.get("interval_s", 0.0))))

    try:
        # short lock is enough for stills
        with CameraLock(timeout_s=8.0):
            for i in range(burst):
                path = capture_image(resolution_key=res)  # capture module decides directory
                size = os.path.getsize(path) if os.path.exists(path) else -1
                print(f"[CAM/IMG] SAVED {path} ({size} bytes) res={res} burst={i+1}/{burst}")

                # ACK to Spotter console
                fn = os.path.basename(path)
                ack_print(ctx, f"OK image file={fn} res={res} bytes={size} idx={i+1}/{burst}")

                if i + 1 < burst and interval_s > 0:
                    time.sleep(interval_s)

    except TimeoutError:
        print("[CAM/IMG][BUSY] camera in use; drop trigger")
        ack_print(ctx, "ERR image reason=busy")
    except Exception as e:
        print(f"[CAM/IMG][ERR] {e!r}")
        ack_print(ctx, f"ERR image reason={type(e).__name__}")
