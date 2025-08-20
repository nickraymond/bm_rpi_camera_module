
# filename: camera_still.py
# description: Bristlemouth handler to capture a still image on command.
# Follows bm_agent handler style: init(ctx), cleanup(ctx), handle(node, topic, data, ctx)

import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

# Resolve project root so we can import camera_software modules
CAM_SOFT_DIR = Path(__file__).resolve().parents[2]  # .../camera_software
if str(CAM_SOFT_DIR) not in sys.path:
    sys.path.append(str(CAM_SOFT_DIR))

from process_image import capture_image, IMAGE_DIRECTORY, validate_resolution  # uses Pi clock in filename

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
        print("[STILL][ERR] invalid JSON payload:", data)
        return {}

def handle(node_id, topic: str, data: bytes, ctx):
    payload = _parse_json(data)
    resolution = payload.get("resolution", "VGA")
    transmit = bool(payload.get("transmit", False))
    try:
        validate_resolution(resolution)  # raises on error
    except Exception as e:
        print(f"[STILL][ERR] {e}")
        return

    try:
        path = capture_image(resolution_key=resolution, directory_path=IMAGE_DIRECTORY)
        size = os.path.getsize(path)
        print(f"[STILL] saved {path} ({size} bytes), tx={transmit}")
    except Exception as e:
        print(f"[STILL][ERR] failed to capture: {e}")

###

# ...top of file...

def _parse_json_typed(data: bytes) -> dict:
    if not data:
        return {}
    # If first byte is a small control (content-type), and next byte starts JSON, strip it
    if len(data) >= 2 and data[0] < 0x20 and data[1] in (ord("{"), ord("[")):
        body = data[1:]
    else:
        body = data
    try:
        return json.loads(body.decode("utf-8", "ignore"))
    except Exception as e:
        print(f"[STILL][ERR] JSON parse failed: {e!r} payload={body[:64]!r}")
        return {}

