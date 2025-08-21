
# filename: capture_image_cmd.py
# description: Placeholder handler for topic 'camera/capture/image' (text-only).
# '1' triggers a placeholder action; any other text is echoed for testing.

def init(ctx):
    pass

def cleanup(ctx):
    pass

def _get_text_payload(data: bytes) -> str:
    if not data:
        return ""
    # Strip 1-byte BM content-type if present (text=small control value)
    body = data[1:] if data and data[0] < 0x20 else data
    s = body.decode("utf-8", "ignore").strip()
    # Strip surrounding quotes if CLI left them in
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1]
    return s

def handle(node_id, topic: str, data: bytes, ctx):
    msg = _get_text_payload(data)
    if msg in ("", "1", "go", "trigger"):
        print("[CAM/IMG] placeholder TRIGGER: would call image_capture.py()")
    else:
        print(f"[CAM/IMG] placeholder MESSAGE: {msg!r}")
