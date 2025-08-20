# filename: video_capture.py
# description: modular functions to record short video clips and save them locally (Py 3.9 compatible)
# Paths are resolved relative to THIS file's directory (like your image_processing.py pattern).
# Any relative path given is resolved under BASE_DIR to avoid writing to $HOME accidentally.

from typing import Union, Optional
from pathlib import Path
from datetime import datetime
import os
import time
import shutil

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput, FileOutput
import libcamera

# ---------------------------
# Directory layout
# ---------------------------
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
VIDEO_DIRECTORY: str = os.path.join(BASE_DIR, "videos")
os.makedirs(VIDEO_DIRECTORY, exist_ok=True)

# ---------------------------
# Camera presets
# ---------------------------
RESOLUTIONS = {
    "12MP": (4056, 3040),
    "8MP": (3264, 2448),
    "5MP": (2592, 1944),
    "4MP": (2464, 1848),
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "VGA": (640, 480),
}

DEFAULT_FPS = 30
DEFAULT_BITRATE = 5_000_000  # bits per second, ~5 Mbps
WARMUP_S = 0.5               # pre-roll to stabilize exposure/fps before encoding

# ---------------------------
# Helpers
# ---------------------------
def _ensure_dir(path: Union[str, Path]) -> str:
    os.makedirs(path, exist_ok=True)
    return str(path)

def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

def _resolve_under_base(p: Union[str, Path]) -> str:
    p_str = os.fspath(p)
    if os.path.isabs(p_str):
        return p_str
    return os.path.join(BASE_DIR, p_str)

def build_video_path(directory_path: Union[str, Path], base_name: str, extension: str = "mp4") -> str:
    directory_path = _ensure_dir(_resolve_under_base(directory_path))
    filename = f"{base_name}_{_timestamp()}.{extension}"
    return os.path.join(directory_path, filename)

# ---------------------------
# Public API
# ---------------------------
def record_video(
    duration_s: float,
    resolution_key: str = "1080p",
    directory_path: Union[str, Path] = VIDEO_DIRECTORY,
    base_name: str = "VID",
    fps: int = DEFAULT_FPS,
    bitrate: int = DEFAULT_BITRATE,
    hflip: bool = False,
    vflip: bool = False,
    explicit_path: Optional[str] = None,
) -> str:
    """Record a short clip and save it.
    - Uses hardware H.264. If `ffmpeg` is available, muxes to MP4 in-place.
      Otherwise falls back to raw .h264 (convert later).
    - Warms up the camera before starting encode to improve duration accuracy.
    Returns: final saved file path ('.mp4' or '.h264').
    """
    assert resolution_key in RESOLUTIONS, "Unknown resolution key: %s" % resolution_key
    width, height = RESOLUTIONS[resolution_key]

    # Output path
    if explicit_path:
        out_path = _resolve_under_base(explicit_path)
        parent = os.path.dirname(out_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    else:
        out_path = build_video_path(directory_path, base_name, extension="mp4")

    picam2 = Picamera2()

    # Use YUV420 for efficient video encoding
    config = picam2.create_video_configuration(
        main={"size": (width, height), "format": "YUV420"},
        controls={"FrameRate": fps},
    )
    if hflip or vflip:
        config["transform"] = libcamera.Transform(hflip=int(hflip), vflip=int(vflip))

    picam2.configure(config)

    # Start the camera first and let it settle, then start the encoder.
    picam2.start()
    # Reinforce frame rate once running
    try:
        picam2.set_controls({"FrameRate": fps})
    except Exception:
        pass
    time.sleep(WARMUP_S)

    encoder = H264Encoder(bitrate=bitrate)

    if shutil.which("ffmpeg") is not None and out_path.lower().endswith(".mp4"):
        output = FfmpegOutput(out_path)  # container inferred from .mp4
        final_path = out_path
    else:
        root, _ = os.path.splitext(out_path)
        final_path = root + ".h264"
        output = FileOutput(final_path)

    try:
        picam2.start_recording(encoder, output)
        time.sleep(float(duration_s))
    finally:
        try:
            picam2.stop_recording()
        except Exception:
            pass
        try:
            picam2.stop()
        except Exception:
            pass
        picam2.close()

    return final_path

def save_video(
    base_name: str,
    duration_s: float,
    resolution_key: str = "1080p",
    directory_path: Union[str, Path] = VIDEO_DIRECTORY,
    **kwargs,
) -> str:
    directory_path = _resolve_under_base(directory_path)
    return record_video(
        duration_s=duration_s,
        resolution_key=resolution_key,
        directory_path=directory_path,
        base_name=base_name,
        **kwargs,
    )

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Record a short clip from the Pi Camera.")
    parser.add_argument("--seconds", type=float, default=5.0, help="Duration in seconds")
    parser.add_argument("--resolution", type=str, default="1080p", choices=list(RESOLUTIONS.keys()))
    parser.add_argument("--dir", type=str, default=VIDEO_DIRECTORY, help="Directory to save videos")
    parser.add_argument("--name", type=str, default="VID", help="Base filename prefix")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS)
    parser.add_argument("--bitrate", type=int, default=DEFAULT_BITRATE, help="H.264 bitrate (bps)")
    parser.add_argument("--hflip", action="store_true")
    parser.add_argument("--vflip", action="store_true")
    parser.add_argument("--explicit_path", type=str, default=None, help="Explicit output path (overrides dir/name)")
    args = parser.parse_args()

    path = record_video(
        duration_s=args.seconds,
        resolution_key=args.resolution,
        directory_path=args.dir,
        base_name=args.name,
        fps=args.fps,
        bitrate=args.bitrate,
        hflip=args.hflip,
        vflip=args.vflip,
        explicit_path=args.explicit_path,
    )
    print(path)
