# # bm_camera/agent/handlers/capture_image_cmd.py
# import logging, os, time
# from pathlib import Path
# from .status_util import send_status  # status via spotter/printf if available
# 
# from bm_camera.utils.camera_lock import CameraLock
# from bm_camera.common.config import get_camera_defaults, get_spotter_tx_settings
# from bm_camera.capture import capture_image
# from bm_camera.encode.file_encoder import get_encoder
# from bm_camera.transport.spotter import (
#     build_base64_chunks, mirror_chunks_to_buffer, send_chunks_to_spotter
# )
# 
# logger = logging.getLogger("IMG")
# 
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
# def _parse_bool(val) -> bool:
#     if isinstance(val, bool):
#         return val
#     v = str(val).strip().lower()
#     return v in ("1","true","yes","on","y")
# 
# def init(ctx): pass
# 
# def cleanup(ctx): pass
# 
# 
# def handle(node_id, topic: str, data: bytes, ctx):
#     from bm_camera.common.config import get_camera_defaults, get_spotter_tx_settings
#     from bm_camera.capture.image_capture import capture_image
#     from bm_camera.encode.file_encoder import get_encoder
#     from bm_camera.transport.spotter import (
#         build_base64_chunks, mirror_chunks_to_buffer, send_chunks_to_spotter
#     )
#     
#     p = _parse_tokens(_payload_to_str(data))
#     defaults = get_camera_defaults("image")
#     
#     # YAML-driven image defaults
#     res      = p.get("res", defaults.get("res", "1080p"))
#     burst    = max(1, int(p.get("burst", defaults.get("burst", 1))))
#     interval = _parse_ms(p["int"]) if "int" in p else float(defaults.get("interval_s", 0.0))
#     
#     # Encoding choices
#     enc_fmt  = p.get("fmt", defaults.get("encode_format", "heif")).lower()
#     quality  = int(p.get("q",   defaults.get("quality", 25)))
#     
#     # Transport gate: default false unless explicitly enabled
#     send_flag = _parse_bool(p.get("send", defaults.get("send_via_spotter", False)))
#     
#     # "Danger Zone" transport tuning (chunk_size / delay_s) from YAML
#     tx_cfg = get_spotter_tx_settings()  # {"chunk_size": 300, "delay_s": 5.0} with YAML overrides
#     
#     bm = ctx.get("bm")
#     
#     try:
#         with CameraLock(timeout_s=8.0):
#             for i in range(burst):
#                 # 1) capture
#                 src_path = Path(capture_image(resolution_key=res))
#                 size_raw = os.path.getsize(src_path) if src_path.exists() else -1
#                 logger.info("[CAM/IMG] CAPTURED %s (%d bytes) res=%s burst=%d/%d",
#                             src_path, size_raw, res, i+1, burst)
#     
#                 # 2) encode
#                 encoder  = get_encoder(enc_fmt)
#                 enc_path = encoder(src_path, quality=quality, suffix="-c")
#                 size_enc = os.path.getsize(enc_path) if enc_path.exists() else -1
#                 logger.info("[ENC] %s -> %s (%d bytes) fmt=%s q=%d",
#                             src_path.name, enc_path.name, size_enc, enc_fmt, quality)
#     
#                 # 3) optional transport
#                 if send_flag:
#                     basename, chunks, raw_len = build_base64_chunks(
#                         enc_path, chunk_size=tx_cfg["chunk_size"]
#                     )
#                     mirror_chunks_to_buffer(chunks, clear_first=True)
#     
#                     # Per-chunk counter appears at DEBUG level inside this function
#                     send_chunks_to_spotter(
#                         bm,
#                         file_label=basename,
#                         chunks=chunks,
#                         delay_s=tx_cfg["delay_s"],
#                         kind="IMG",
#                     )
#                     tx = "yes"
#                     logger.info("[TX] sent via Spotter: %s (%d chunks)", basename, len(chunks))
#                 else:
#                     tx = "no"
#                     logger.info("[TX] skipped (send flag false)")
#     
#                 # Status ACK back to Spotter terminal
#                 from .status_util import send_status
#                 send_status(
#                     ctx, "OK",
#                     op="image",
#                     file=os.path.basename(enc_path),
#                     res=res, idx=i+1, burst=burst, bytes=size_enc, tx=tx
#                 )
#     
#                 if i + 1 < burst and interval > 0:
#                     time.sleep(interval)
#     
#     except TimeoutError:
#         from .status_util import send_status
#         logger.warning("[CAM/IMG][BUSY] camera in use; drop trigger")
#         send_status(ctx, "BUSY", op="image")
#     except Exception as e:
#         from .status_util import send_status
#         logger.exception("[CAM/IMG][ERR] %r", e)
#         send_status(ctx, "ERR", op="image", reason=type(e).__name__)

# Trying this to add more robus logging and dedpue handling
import logging
import os, sys, time
from pathlib import Path

from bm_camera.utils.camera_lock import CameraLock

# Ensure camera_software is importable in dev shells
CAMERA_SW_DIR = Path(__file__).resolve().parents[3]
sp = str(CAMERA_SW_DIR)
if sp not in sys.path:
    sys.path.insert(0, sp)

from bm_camera.capture.image_capture import capture_image
from bm_camera.encode.file_encoder import get_encoder
from bm_camera.transport.spotter import (
    build_base64_chunks,
    mirror_chunks_to_buffer,
    send_chunks_to_spotter,
    get_spotter_tx_settings,
)
from bm_camera.common.config import get_camera_defaults
from .status_util import send_status

log = logging.getLogger("IMG")


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

def _parse_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    v = str(val).strip().lower()
    return v in ("1","true","yes","on","y")

def init(ctx): pass
def cleanup(ctx): pass


def handle(node_id, topic: str, data: bytes, ctx):
    p = _parse_tokens(_payload_to_str(data))
    defaults = get_camera_defaults("image")

    # YAML-driven image capture defaults
    res       = p.get("res", defaults.get("res", "1080p"))
    burst     = max(1, int(p.get("burst", defaults.get("burst", 1))))
    interval  = _parse_ms(p["int"]) if "int" in p else float(defaults.get("interval_s", 0.0))
    enc_fmt   = p.get("fmt", defaults.get("encode_format", "heif")).lower()
    quality   = int(p.get("q",   defaults.get("quality", 25)))

    # transport gate (default false unless explicitly enabled)
    send_flag = _parse_bool(p.get("send", defaults.get("send_via_spotter", False)))

    bm = ctx.get("bm")

    # ---- EARLY ACK: confirm receipt to upstream immediately ----
    try:
        send_status(ctx, "ACK", op="image", stage="recv")
    except Exception:
        # never fail the capture because of an ACK
        log.debug("status ACK failed (non-fatal)", exc_info=True)

    try:
        with CameraLock(timeout_s=8.0):
            for i in range(burst):
                # 1) capture
                src_path = Path(capture_image(resolution_key=res))
                size_raw = os.path.getsize(src_path) if src_path.exists() else -1
                log.info("[CAM/IMG] CAPTURED %s (%d bytes) res=%s burst=%d/%d",
                         src_path, size_raw, res, i+1, burst)

                # 2) encode
                encoder  = get_encoder(enc_fmt)
                enc_path = encoder(src_path, quality=quality, suffix="-c")
                size_enc = os.path.getsize(enc_path) if enc_path.exists() else -1
                log.info("[ENC] %s -> %s (%d bytes) fmt=%s q=%d",
                         src_path.name, enc_path.name, size_enc, enc_fmt, quality)

                # 3) optional transport
                if send_flag:
                    tx_cfg = get_spotter_tx_settings()
                    basename, chunks, raw_len = build_base64_chunks(
                        enc_path, chunk_size=tx_cfg["chunk_size"]
                    )
                    mirror_chunks_to_buffer(chunks, clear_first=True)
                    log.info("[TX] START %s chunks=%d", basename, len(chunks))
                    send_chunks_to_spotter(
                        bm,
                        file_label=basename,
                        chunks=chunks,
                        delay_s=tx_cfg["delay_s"],
                        kind="IMG",
                    )
                    log.info("[TX] END %s", basename)
                    tx = "yes"
                    log.info("[TX] sent via Spotter: %s (%d chunks)", basename, len(chunks))
                else:
                    tx = "no"
                    log.info("[TX] skipped (send flag false)")

                # status ACK (result)
                send_status(ctx, "OK", op="image", file=os.path.basename(enc_path),
                            res=res, idx=i+1, burst=burst, bytes=size_enc, tx=tx)

                # next in burst
                if i + 1 < burst and interval > 0:
                    time.sleep(interval)

    except TimeoutError:
        log.warning("[CAM/IMG][BUSY] camera in use; drop trigger")
        send_status(ctx, "BUSY", op="image")
    except Exception as e:
        log.exception("[CAM/IMG][ERR] %r", e)
        send_status(ctx, "ERR", op="image", reason=type(e).__name__)
