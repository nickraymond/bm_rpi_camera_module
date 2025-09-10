# bm_camera/encode/file_encoder.py
from pathlib import Path
from typing import Literal, Callable
from PIL import Image

# HEIF support; gracefully degrade to JPEG if pillow_heif missing
_HEIF_OK = False
try:
	import pillow_heif  # type: ignore
	pillow_heif.register_heif_opener()
	_HEIF_OK = True
except Exception:
	_HEIF_OK = False


def _out_path(src: Path, *, new_ext: str, suffix: str) -> Path:
	# src: /path/foo.jpg  -> /path/foo-c.jpg (or .heic)
	return src.with_name(src.stem + suffix + new_ext)


def compress_to_jpeg(src: Path, *, quality: int = 75, suffix: str = "-c") -> Path:
	"""
	Re-encode to JPEG with given quality. Keeps it simple (RGB, no metadata).
	Returns the new file path.
	"""
	src = Path(src)
	dst = _out_path(src, new_ext=".jpg", suffix=suffix)
	with Image.open(src) as img:
		if img.mode not in ("RGB", "L"):
			img = img.convert("RGB")
		dst.parent.mkdir(parents=True, exist_ok=True)
		img.save(dst, format="JPEG", quality=int(quality), optimize=True)
	return dst


def compress_to_heif(src: Path, *, quality: int = 50, suffix: str = "-c") -> Path:
	"""
	Encode to HEIF/HEIC if available; otherwise falls back to JPEG.
	Returns the new file path.
	"""
	if not _HEIF_OK:
		# fallback to jpeg if HEIF support is unavailable
		return compress_to_jpeg(src, quality=quality, suffix=suffix)

	src = Path(src)
	dst = _out_path(src, new_ext=".heic", suffix=suffix)
	with Image.open(src) as img:
		if img.mode not in ("RGB", "L"):
			img = img.convert("RGB")
		dst.parent.mkdir(parents=True, exist_ok=True)
		# pillow-heif uses same 1..100-ish quality scale
		img.save(dst, format="HEIF", quality=int(quality))
	return dst


Format = Literal["jpeg", "heif"]

def get_encoder(fmt: Format) -> Callable[..., Path]:
	"""
	Map a format string to an encoder function.
	"""
	f = fmt.lower().strip()
	if f in ("jpeg", "jpg", "image/jpeg"):
		return compress_to_jpeg
	if f in ("heif", "heic", "image/heif", "image/heic"):
		return compress_to_heif
	# default sensible choice
	return compress_to_heif if _HEIF_OK else compress_to_jpeg
