# camera_lock.py
import os, time, fcntl

class CameraLock:
	"""
	Simple cross-process lock using fcntl.flock on a lockfile.
	Prevents concurrent still/video operations from different handlers/processes.
	"""
	def __init__(self, path="/tmp/bm_daemon.capture.lock", timeout_s=10.0, poll_s=0.05):
		self.path = path
		self.timeout_s = float(timeout_s)
		self.poll_s = float(poll_s)
		self.fd = None

	def acquire(self) -> bool:
		start = time.monotonic()
		# create/open the lockfile
		self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o666)
		while True:
			try:
				fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
				# optional: write our PID for debugging
				try:
					os.ftruncate(self.fd, 0)
					os.write(self.fd, str(os.getpid()).encode("ascii"))
				except Exception:
					pass
				return True
			except BlockingIOError:
				if time.monotonic() - start >= self.timeout_s:
					return False
				time.sleep(self.poll_s)

	def release(self):
		if self.fd is not None:
			try:
				fcntl.flock(self.fd, fcntl.LOCK_UN)
			finally:
				os.close(self.fd)
				self.fd = None

	def __enter__(self):
		if not self.acquire():
			raise TimeoutError(f"CameraLock: timeout after {self.timeout_s}s")
		return self

	def __exit__(self, exc_type, exc, tb):
		self.release()
