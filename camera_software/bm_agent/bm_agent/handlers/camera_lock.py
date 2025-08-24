# one process-wide lock for camera access (stills & video)
import threading
LOCK = threading.Lock()
