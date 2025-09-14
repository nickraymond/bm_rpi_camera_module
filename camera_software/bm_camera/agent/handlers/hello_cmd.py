

#!/usr/bin/env python3
import logging

logger = logging.getLogger("HELLO")

def _payload_to_str(data: bytes) -> str:
    """Decode BM payload to a clean string (strip 1B type if present, trim quotes)."""
    if not data:
        return ""
    body = data[1:] if data and data[0] < 0x20 else data  # BM sometimes prefixes a type byte
    s = body.decode("utf-8", "ignore").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1]
    return s

def _ack_topic(ctx: dict, topic_in: str) -> str:
    """Ack topic from YAML if defined (topics.hello_ack), else '<topic>/ack'."""
    cfg = (ctx or {}).get("cfg") or {}
    topics = (cfg.get("topics") or {})
    return topics.get("hello_ack") or f"{topic_in}/ack"

def _ack_print(ctx: dict, message: str) -> None:
    """
    Print an ACK line on the Spotter/Bridge console if possible; otherwise log it.
    Mirrors the status_util.ack_print behavior but local to this handler.
    """
    bm = (ctx or {}).get("bm")
    if bm and hasattr(bm, "spotter_print"):
        try:
            bm.spotter_print(message)
            logger.debug("spotter_print: %s", message)
            return
        except Exception as e:
            logger.warning("spotter_print failed: %r", e)
    logger.info("[ACK] %s", message)

def _publish_text(bm, topic: str, text: str) -> bool:
    """
    Publish a TEXT frame to the BM bus.
    Try your wrapper if present; fall back to raw bristlemouth_publish.
    TEXT type is 0 in your system.
    """
    # Path A: your project wrapper (if available)
    try:
        from bm_camera.agent.publish import bristlemouth_pub
        bristlemouth_pub(bm, topic, text, 0, header_version=1)
        return True
    except Exception:
        pass

    # Path B: raw bus method
    if hasattr(bm, "bristlemouth_publish"):
        bm.bristlemouth_publish(topic, text.encode("utf-8"), 0, header_version=1)
        return True

    return False

def handle(node_id: int, topic_str: str, data: bytes, ctx: dict) -> None:
    """
    Receive 'demo/hello', print an ACK line to the Bridge console, and publish an ACK frame.
    """
    txt = _payload_to_str(data)
    logger.info("HELLO rx node=%s topic=%s payload=%r", hex(node_id), topic_str, txt)

    # Show something immediately on the Bridge console (non-BM side)
    _ack_print(ctx, f"ack hello: {txt}")

    # Publish a real ACK frame onto the BM bus so subscribers can receive it
    bm = (ctx or {}).get("bm")
    if not bm:
        logger.warning("ACK not sent: bm not in ctx")
        return

    ack_topic = _ack_topic(ctx, topic_str)
    if _publish_text(bm, ack_topic, txt):
        logger.info("ACK -> %s (%r)", ack_topic, txt)
    else:
        logger.warning("ACK not sent: publish helpers missing")
