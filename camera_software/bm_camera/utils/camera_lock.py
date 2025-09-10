import threading

# One global lock guarding the camera hardware.
_cam_lock = threading.Lock()

class CameraLock:
    """
    Context manager to serialize access to the camera.
    Usage:
        with CameraLock(timeout_s=8.0):
            ... use camera ...
    Raises TimeoutError if the camera is busy for longer than timeout.
    """
    def __init__(self, timeout_s: float = 8.0):
        self.timeout_s = float(timeout_s)

    def __enter__(self):
        ok = _cam_lock.acquire(timeout=self.timeout_s)
        if not ok:
            raise TimeoutError("camera in use")
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            _cam_lock.release()
        except Exception:
            pass
        return False
