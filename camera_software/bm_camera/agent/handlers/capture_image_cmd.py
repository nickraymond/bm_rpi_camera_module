# # bm_camera/agent/handlers/capture_image_cmd.py
# import logging
# import os, sys, time
# from pathlib import Path
# from camera_lock import CameraLock
# 
# logger = logging.getLogger("bm_camera.image")
# 
# # make camera_software visible on sys.path
# CAMERA_SW_DIR = Path(__file__).resolve().parents[3]
# sp = str(CAMERA_SW_DIR)
# if sp not in sys.path:
#     sys.path.insert(0, sp)
# 
# from image_capture import capture_image  # image module handles output dir
# from bm_camera.common.config import get_camera_defaults
# from .status_util import send_status  # uses spotter_print() if available
# 
# def debug_print(message: str):
#     logger.debug(message)
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
# def init(ctx):  # nothing needed; image_capture ensures dirs
#     pass
# 
# def cleanup(ctx):
#     pass
# 
# def handle(node_id, topic: str, data: bytes, ctx):
#     params = _parse_tokens(_payload_to_str(data))
#     defaults = get_camera_defaults("image")
# 
#     res = params.get("res", defaults["res"])
#     burst = max(1, int(params.get("burst", defaults["burst"])))
#     interval_s = float(params.get("int", defaults["interval_s"])) if "int" in params else defaults["interval_s"]
# 
#     try:
#         with CameraLock(timeout_s=8.0):
#             for i in range(burst):
#                 path = capture_image(resolution_key=res)  # module uses YAML paths
#                 size = os.path.getsize(path) if os.path.exists(path) else -1
#                 logger.info(
#                     "[CAM/IMG] SAVED {path} ({size} bytes) res={res} burst={i+1}/{burst}")
#                 send_status(ctx, "OK", op="image", file=os.path.basename(path), res=res, idx=i+1, burst=burst, bytes=size)
#                 if i + 1 < burst and interval_s > 0:
#                     time.sleep(interval_s)
#     except TimeoutError:
#         logger.warning("[CAM/IMG][BUSY] camera in use; drop trigger")
#         send_status(ctx, "BUSY", op="image")
#     except Exception as e:
#         logger.exception("[CAM/IMG][ERR] {e!r}")
#         send_status(ctx, "ERR", op="image", reason=type(e).__name__)
# bm_camera/agent/handlers/capture_image_cmd.py
import logging
import os, sys, time
from pathlib import Path
from camera_lock import CameraLock

logger = logging.getLogger("bm_camera.image")

# make camera_software visible on sys.path
CAMERA_SW_DIR = Path(__file__).resolve().parents[3]
sp = str(CAMERA_SW_DIR)
if sp not in sys.path:
    sys.path.insert(0, sp)

from image_capture import capture_image  # image module handles output dir
from bm_camera.common.config import get_camera_defaults
from .status_util import send_status  # uses spotter_print() if available

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

def init(ctx):
    pass  # image_capture ensures directories

def cleanup(ctx):
    pass

def handle(node_id, topic: str, data: bytes, ctx):
    params = _parse_tokens(_payload_to_str(data))
    defaults = get_camera_defaults("image")

    res = params.get("res", defaults["res"])
    burst = max(1, int(params.get("burst", defaults["burst"])))
    interval_s = _parse_ms(params["int"]) if "int" in params else float(defaults["interval_s"])

    try:
        with CameraLock(timeout_s=8.0):
            for i in range(burst):
                path = capture_image(resolution_key=res)  # module uses YAML paths
                size = os.path.getsize(path) if os.path.exists(path) else -1

                # Correct parameterized logging
                logger.info(
                    "[CAM/IMG] SAVED %s (%d bytes) res=%s burst=%d/%d",
                    path, size, res, i + 1, burst
                )

                send_status(
                    ctx, "OK",
                    op="image",
                    file=os.path.basename(path),
                    res=res,
                    idx=i + 1,
                    burst=burst,
                    bytes=size,
                )

                if i + 1 < burst and interval_s > 0:
                    time.sleep(interval_s)

    except TimeoutError:
        logger.warning("[CAM/IMG][BUSY] camera in use; drop trigger")
        send_status(ctx, "BUSY", op="image")

    except Exception as e:
        # Include traceback
        logger.exception("[CAM/IMG][ERR] %r", e)
        send_status(ctx, "ERR", op="image", reason=type(e).__name__)

