# filename: test_pi.py
# description: Minimal text-only handler for topic "test/pi".
# Prints either a default message or the provided text payload.

def init(ctx):
	pass

def cleanup(ctx):
	pass

def _get_text_payload(data: bytes) -> str:
	if not data:
		return ""
	# BM adds a 1-byte content-type tag; for 'text' it's a small control byte.
	body = data[1:] if data and data[0] < 0x20 else data
	try:
		return body.decode("utf-8", "ignore").strip()
	except Exception:
		return ""

def handle(node_id, topic: str, data: bytes, ctx):
	msg = _get_text_payload(data)
	if msg in ("", "1", "go", "trigger"):   # default trigger
		print("[TEST/PI] default trigger received")
	else:
		print(f"[TEST/PI] message: {msg}")
