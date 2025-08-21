
# filename: capture_video_cmd.py
# description: Placeholder handler for topic 'camera/capture/video' (text-only).
# '1' triggers a placeholder action; any other text is echoed for testing.

def init(ctx):
    pass

def cleanup(ctx):
    pass

def _get_text_payload(data: bytes) -> str:
    if not data:
        return ""
    body = data[1:] if data and data[0] < 0x20 else data
    s = body.decode("utf-8", "ignore").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1]
    return s

def handle(node_id, topic: str, data: bytes, ctx):
    msg = _get_text_payload(data)
    if msg in ("", "1", "go", "trigger"):
        print("[CAM/VID] placeholder TRIGGER: would call video_capture.py()")
    else:
        print(f"[CAM/VID] placeholder MESSAGE: {msg!r}")
