# filename capture_image_cmd.py
import os, sys, time
from pathlib import Path
from camera_lock import CameraLock


# make camera_software visible on sys.path
CAMERA_SW_DIR = Path(__file__).resolve().parents[3]
sp = str(CAMERA_SW_DIR)
if sp not in sys.path:
    sys.path.insert(0, sp)

# import the still module
from image_capture import capture_image, IMAGE_DIRECTORY  # keep as 'process_image' for now

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
    try:
        os.makedirs(IMAGE_DIRECTORY, exist_ok=True)
    except Exception:
        pass

def cleanup(ctx):
    pass

# Blocking definition
# def handle(node_id, topic: str, data: bytes, ctx):
#     params = _parse_tokens(_payload_to_str(data))
#     res = params.get("res", "1080p")
#     burst = max(1, int(params.get("burst", 1)))
#     interval_s = _parse_ms(params["int"]) if "int" in params else 0.0
#     
#     try:
#         # Short lock is enough for warmup + single/burst stills
#         with CameraLock(timeout_s=8.0):
#             for i in range(burst):
#                 path = capture_image(resolution_key=res, directory_path=IMAGE_DIRECTORY)
#                 size = os.path.getsize(path) if os.path.exists(path) else -1
#                 print(f"[CAM/IMG] SAVED {path} ({size} bytes) res={res} burst={i+1}/{burst}")
#                 if i + 1 < burst and interval_s > 0:
#                     time.sleep(interval_s)
#     except TimeoutError:
#         print("[CAM/IMG][BUSY] camera in use; drop trigger")
#     except Exception as e:
#         print(f"[CAM/IMG][ERR] {e!r}")
def handle(node_id, topic: str, data: bytes, ctx):
    params = _parse_tokens(_payload_to_str(data))
    res = params.get("res", "1080p")
    burst = max(1, int(params.get("burst", 1)))
    interval_s = _parse_ms(params["int"]) if "int" in params else 0.0
    
    # Non-blocking: try once, drop if busy
    lock = CameraLock(timeout_s=0.0)
    if not lock.acquire():
        print("[CAM/IMG][BUSY] camera in use; drop trigger")
        return
    
    try:
        for i in range(burst):
            path = capture_image(resolution_key=res, directory_path=IMAGE_DIRECTORY)
            size = os.path.getsize(path) if os.path.exists(path) else -1
            print(f"[CAM/IMG] SAVED {path} ({size} bytes) res={res} burst={i+1}/{burst}")
            if i + 1 < burst and interval_s > 0:
                time.sleep(interval_s)
    except Exception as e:
        print(f"[CAM/IMG][ERR] {e!r}")
    finally:
        lock.release()

