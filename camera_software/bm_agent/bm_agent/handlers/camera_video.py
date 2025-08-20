
# filename: camera_video.py
# description: Bristlemouth handler to record a video clip on command.
# Follows bm_agent handler style: init(ctx), cleanup(ctx), handle(node, topic, data, ctx)

import json
import os
import sys
from pathlib import Path

# Resolve project root so we can import camera_software modules
CAM_SOFT_DIR = Path(__file__).resolve().parents[2]  # .../camera_software
if str(CAM_SOFT_DIR) not in sys.path:
    sys.path.append(str(CAM_SOFT_DIR))

from video_capture import save_video, VIDEO_DIRECTORY, RESOLUTIONS  # names files with Pi clock timestamp

def init(ctx):
    pass

def cleanup(ctx):
    pass

def _parse_json(data: bytes):
    if not data:
        return {}
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:
        print("[VIDEO][ERR] invalid JSON payload:", data)
        return {}

def handle(node_id, topic: str, data: bytes, ctx):
    payload = _parse_json(data)
    resolution = payload.get("resolution", "720p")
    duration_s = float(payload.get("duration_s", 3.0))
    fps = int(payload.get("fps", 30))
    bitrate = int(payload.get("bitrate", 5_000_000))
    hflip = bool(payload.get("hflip", False))
    vflip = bool(payload.get("vflip", False))
    transmit = bool(payload.get("transmit", False))

    if resolution not in RESOLUTIONS:
        print(f"[VIDEO][ERR] invalid resolution '{resolution}'. Choose one of: {', '.join(RESOLUTIONS.keys())}")
        return

    try:
        path = save_video(
            base_name="VID",
            duration_s=duration_s,
            resolution_key=resolution,
            directory_path=VIDEO_DIRECTORY,
            fps=fps,
            bitrate=bitrate,
            hflip=hflip,
            vflip=vflip,
        )
        size = os.path.getsize(path)
        print(f"[VIDEO] saved {path} ({size} bytes), tx={transmit}, fps={fps}, bitrate={bitrate}")
    except Exception as e:
        print(f"[VIDEO][ERR] failed to record: {e}")

# ...top of file...

def _parse_json_typed(data: bytes) -> dict:
    if not data:
        return {}
    if len(data) >= 2 and data[0] < 0x20 and data[1] in (ord("{"), ord("[")):
        body = data[1:]
    else:
        body = data
    try:
        return json.loads(body.decode("utf-8", "ignore"))
    except Exception as e:
        print(f"[VIDEO][ERR] JSON parse failed: {e!r} payload={body[:64]!r}")
        return {}

