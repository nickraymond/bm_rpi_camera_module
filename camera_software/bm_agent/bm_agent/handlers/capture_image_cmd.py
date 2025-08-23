# 
# # filename: capture_image_cmd.py
# # description: Placeholder handler for topic 'camera/capture/image' (text-only).
# # '1' triggers a placeholder action; any other text is echoed for testing.
# 
# def init(ctx):
#     pass
# 
# def cleanup(ctx):
#     pass
# 
# def _get_text_payload(data: bytes) -> str:
#     if not data:
#         return ""
#     # Strip 1-byte BM content-type if present (text=small control value)
#     body = data[1:] if data and data[0] < 0x20 else data
#     s = body.decode("utf-8", "ignore").strip()
#     # Strip surrounding quotes if CLI left them in
#     if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
#         s = s[1:-1]
#     return s
# 
# def handle(node_id, topic: str, data: bytes, ctx):
#     msg = _get_text_payload(data)
#     if msg in ("", "1", "go", "trigger"):
#         print("[CAM/IMG] placeholder TRIGGER: would call image_capture.py()")
#     else:
#         print(f"[CAM/IMG] placeholder MESSAGE: {msg!r}")
# text-only handler for topic 'camera/capture/image'
# Usage examples:
#   bm pub camera/capture/image 1 text 0
#   bm pub camera/capture/image res=1080p,burst=3,int=200ms text 0
import os, time, sys
from pathlib import Path

# --- make camera_software visible for imports ---
CAMERA_SW_DIR = Path(__file__).resolve().parents[3]  # .../camera_software
if str(CAMERA_SW_DIR) not in sys.path:
    sys.path.insert(0, str(CAMERA_SW_DIR))

# --- import the still image module ---
from process_image import capture_image, IMAGE_DIRECTORY  # your module/file name

# -------- helpers --------
def _payload_to_str(data: bytes) -> str:
    if not data:
        return ""
    body = data[1:] if data and data[0] < 0x20 else data  # strip 1B BM type
    s = body.decode("utf-8", "ignore").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1]
    return s

def _parse_tokens(s: str) -> dict:
    # Accept: '1' (defaults), '1080p' (resolution), or key=value CSV
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
    # '200ms' -> 0.2, '1s' -> 1.0, '0.5' -> 0.5
    v = val.lower()
    if v.endswith("ms"):
        return float(v[:-2]) / 1000.0
    if v.endswith("s"):
        return float(v[:-1])
    return float(v)

# -------- handler --------
def init(ctx):  # no-op is fine
    # Ensure images dir exists if module didn't create it
    try:
        os.makedirs(IMAGE_DIRECTORY, exist_ok=True)
    except Exception:
        pass

def cleanup(ctx):
    pass

def handle(node_id, topic: str, data: bytes, ctx):
    s = _payload_to_str(data)
    params = _parse_tokens(s)

    res = params.get("res", "1080p")
    burst = int(params.get("burst", 1))
    interval_s = _parse_ms(params["int"]) if "int" in params else 0.0

    try:
        for i in range(max(1, burst)):
            # Call your still capture function.
            # If your function takes different args, adjust here:
            # e.g., capture_image(resolution_key=res, directory_path=IMAGE_DIRECTORY)
            path = capture_image(resolution_key=res, directory_path=IMAGE_DIRECTORY)  # <- adjust if needed
            try:
                size = os.path.getsize(path)
            except Exception:
                size = -1
            print(f"[CAM/IMG] SAVED {path} ({size} bytes) res={res} burst={i+1}/{burst}")
            if i + 1 < burst and interval_s > 0:
                time.sleep(interval_s)
    except Exception as e:
        print(f"[CAM/IMG][ERR] {e!r}")
