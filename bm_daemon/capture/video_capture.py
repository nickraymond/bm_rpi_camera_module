# file video_capture.py
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import shutil
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput, FileOutput

from bm_daemon.common.paths import video_dir
from bm_daemon.common.config import get_resolutions
from bm_daemon.common.config import resolve_resolution
from bm_daemon.utils.camera_lock import CameraLock



# --- paths ---
BASE_DIR = Path(__file__).resolve().parent

VIDEO_DIRECTORY = Path(video_dir())  # was previously computed locally
VIDEO_DIRECTORY.mkdir(parents=True, exist_ok=True)


# --- resolutions map (YAML-first, with fallback) ---
_RES_FROM_YAML = get_resolutions()
# if _RES_FROM_YAML:
#     RESOLUTIONS = _RES_FROM_YAML
# else:
#     # Fallback only for standalone use or missing YAML
#     RESOLUTIONS = {
#         "12MP": (4056, 3040),
#         "8MP":  (3264, 2448),
#         "5MP":  (2592, 1944),
#         "4MP":  (2464, 1848),
#         "1080p": (1920, 1080),
#         "720p":  (1280, 720),
#         "VGA":   (640, 480),
#     }

def _validate_resolution(key):
    if key not in RESOLUTIONS:
        raise ValueError("Invalid resolution key. Choose from: %s" % ", ".join(sorted(RESOLUTIONS.keys())))
    return RESOLUTIONS[key]

def _ts():
    # UTC ISO-like without separators for filenames
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def _has_ffmpeg():
    return shutil.which("ffmpeg") is not None

def record_video(duration_s=3.0,
                 resolution_key="720p",
                 fps=30,
                 bitrate=3_000_000,
                 directory_path=None,
                 base_name="VID",
                 hflip=False,
                 vflip=False):
    """
    Record a short video and return the saved file path (str).
    Uses MP4 via ffmpeg when available, otherwise .h264 elementary stream.
    """
    if directory_path is None:
        directory_path = str(VIDEO_DIRECTORY)
    outdir = Path(directory_path)
    outdir.mkdir(parents=True, exist_ok=True)

    # size = _validate_resolution(resolution_key)
    size = resolve_resolution(resolution_key)

    ts = _ts()
    ext = ".mp4" if _has_ffmpeg() else ".h264"
    out_path = outdir / f"{base_name}_{ts}{ext}"

    picam2 = Picamera2()
    enc = H264Encoder(bitrate=bitrate)

    # Configure video stream
    config = picam2.create_video_configuration(main={"size": size, "format": "YUV420"}, controls={})
    # Optional flips via controls; safe across libcamera builds
    if hflip:
        config["controls"] = dict(config.get("controls", {}), HorizontalFlip=True)
    if vflip:
        config["controls"] = dict(config.get("controls", {}), VerticalFlip=True)

    try:
        picam2.configure(config)

        if ext == ".mp4":
            output = FfmpegOutput(str(out_path))
        else:
            output = FileOutput(str(out_path))

        picam2.start()
        # Start encoder with PTS when supported (quiet ffmpeg timestamp warnings)
        try:
            picam2.start_recording(enc, output, pts="system")
        except TypeError:
            picam2.start_recording(enc, output)

        # Allow FPS hint (Picamera2 respects in config; this is a gentle sleep gate)
        t_end = time.time() + float(duration_s)
        while time.time() < t_end:
            time.sleep(0.01)

        picam2.stop_recording()
        return str(out_path)

    finally:
        try:
            picam2.stop()
        except Exception:
            pass
        try:
            picam2.close()
        except Exception:
            pass
        time.sleep(0.05)  # small settle

def capture_video(base_name="VID",
               duration_s=3.0,
               resolution_key="720p",
               directory_path=None,
               fps=30,
               bitrate=3_000_000,
               hflip=False,
               vflip=False):
    """Convenience wrapper kept for compatibility."""
    return record_video(duration_s=duration_s,
                        resolution_key=resolution_key,
                        fps=fps,
                        bitrate=bitrate,
                        directory_path=directory_path,
                        base_name=base_name,
                        hflip=hflip,
                        vflip=vflip)
