#!/usr/bin/env python3
from bm_serial import BristlemouthSerial
from datetime import datetime, timezone
import struct, binascii, sys, time

# -------- make ready for automating ------
import signal
_running = True
def _handle_term(signum, frame):
    global _running
    _running = False
signal.signal(signal.SIGTERM, _handle_term)

# ---------- helpers ----------

def _h(bytes_like: bytes, max_len=120) -> str:
    hx = binascii.hexlify(bytes_like).decode()
    return hx if len(hx) <= max_len else hx[:max_len] + "..."

def _decode_topic(topic) -> str:
    if isinstance(topic, (bytes, bytearray)):
        try:
            return topic.decode("utf-8", "ignore")
        except Exception:
            return str(topic)
    return str(topic)

def _plausible_epoch_us(val: int) -> bool:
    # 2000-01-01 .. 2100-01-01 in microseconds
    return 946684800_000000 <= val <= 4102444800_000000

# ---------- time decoding (generic fallback) ----------

def pretty_print_time_from_payload(data: bytes):
    """
    Generic decoder used only when our 8-byte µs fast-path doesn't match.
    """
    # 8 bytes: epoch (ns/us/ms/s) chosen by magnitude
    if len(data) == 8:
        (val,) = struct.unpack("<Q", data)
        if val >= 10**18:
            ts = val / 1e9; unit = "ns"
        elif val >= 10**15:
            ts = val / 1e6; unit = "µs"
        elif val >= 10**11:
            ts = val / 1e3; unit = "ms"
        else:
            ts = float(val); unit = "s"
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        print(f"[utc-time] {dt.isoformat()} (interpreted as {unit} since epoch)")
        return

    # 12 bytes: seconds (u64) + nanos (u32)
    if len(data) == 12:
        sec, nanos = struct.unpack("<QI", data)
        dt = datetime.fromtimestamp(sec + nanos/1e9, tz=timezone.utc)
        print(f"[utc-time] {dt.isoformat()} (sec+nanos)")
        return

    # ISO-8601-ish text
    try:
        s = data.decode("utf-8").strip()
        if any(c in s for c in ("T","Z",":")) and len(s) >= 10:
            print(f"[utc-time] {s} (ASCII/ISO-8601)")
            return
    except UnicodeDecodeError:
        pass

    # Fallback: hex
    print(f"[utc-time] 0x{data.hex()} (unknown format)")

# ---------- subscription callback (single source of truth) ----------

def rtc_cb(node_id, type_, version, topic_len, topic, data_len, data: bytes):
    # Always start PUB on a fresh line (separates from heartbeat dots)
    print()

    topic_str = _decode_topic(topic)

    # Header without raw data dump (keeps logs clean)
    print(f"[BM:PUB→CB] node={hex(node_id)} type={type_} ver={version} topic='{topic_str}' len={data_len}")

    # Fast-path: first 8 bytes are epoch microseconds (covers short + stamped payloads)
    if len(data) >= 8:
        (ts_us,) = struct.unpack("<Q", data[:8])
        if _plausible_epoch_us(ts_us):
            dt = datetime.fromtimestamp(ts_us / 1e6, tz=timezone.utc)
            stamp_note = " (stamped payload)" if len(data) > 8 else ""
            print(f"[utc-time] {dt.isoformat()} (µs since epoch){stamp_note}")
            return

    # Fallback: let the generic decoder try other shapes
    pretty_print_time_from_payload(data)

# ---------- UART safety / TX logging ----------

def _install_uart_safety(bm):
    uart = getattr(bm, "uart", None)
    if uart is None:
        print("[WARN] bm.uart not found; cannot adjust serial parameters", file=sys.stderr)
        return
    try:
        uart.timeout = 0.1
        uart.write_timeout = 0.5
        if hasattr(uart, "rtscts"):  uart.rtscts = False
        if hasattr(uart, "dsrdtr"):  uart.dsrdtr = False
        if hasattr(uart, "xonxoff"): uart.xonxoff = False
        print(f"[UART] port={uart.port} 115200 8N1, timeout={uart.timeout}, write_timeout={uart.write_timeout}, "
              f"rtscts={getattr(uart, 'rtscts', None)}, dsrdtr={getattr(uart, 'dsrdtr', None)}, "
              f"xonxoff={getattr(uart, 'xonxoff', None)}")
    except Exception as e:
        print(f"[UART][WARN] could not tweak UART settings: {e}", file=sys.stderr)

def _patch_tx_write(bm):
    import serial
    def safe_write(bytes_: bytes) -> bool:
        uart = getattr(bm, "uart", None)
        if uart is None:
            print("[BM:TX][ERROR] no underlying UART", file=sys.stderr)
            return False
        try:
            try:
                uart.reset_output_buffer()
            except Exception:
                pass
            print(f"[BM:SUB→TX] {len(bytes_)}B frame=0x{_h(bytes_)}")
            n = uart.write(bytes_)
            uart.flush()
            ok = (n == len(bytes_))
            print(f"[BM:TX] wrote {n}/{len(bytes_)} bytes (ok={ok})")
            return ok
        except serial.SerialTimeoutException:
            print("[BM:TX][ERROR] serial write timed out (write_timeout hit)")
            return False
        except Exception as e:
            print(f"[BM:TX][ERROR] {type(e).__name__}: {e}")
            return False
    if hasattr(bm, "lock_uart_and_write_bytes"):
        bm.lock_uart_and_write_bytes = safe_write
        print("[PATCH] bm.lock_uart_and_write_bytes → safe_write")
    else:
        print("[PATCH][WARN] bm.lock_uart_and_write_bytes not found; cannot patch", file=sys.stderr)

# ---------- main ----------

# def main():
#     bm = BristlemouthSerial()  # opens /dev/serial0 (preferred) or /dev/ttyAMA0
#     print(f"[UART-OPEN] {bm.uart.name} open={bm.uart.is_open}")
# 
#     _install_uart_safety(bm)
#     _patch_tx_write(bm)
# 
#     topic = "spotter/utc-time"
#     print(f"[SUB] subscribing to '{topic}' …")
#     bm.bristlemouth_sub(topic, rtc_cb)
# 
#     print("[RUN] waiting for publishes…  (Ctrl+C to exit)")
#     try:
#         while True:
#             had = bm.bristlemouth_process(0.1)
#             if not had:
#                 print(".", end="", flush=True)
#     except KeyboardInterrupt:
#         print("\n[EXIT] KeyboardInterrupt")
def main():
    bm = BristlemouthSerial()
    print(f"[UART-OPEN] {bm.uart.name} open={bm.uart.is_open}")
    
    _install_uart_safety(bm)
    _patch_tx_write(bm)
    
    topic = "spotter/utc-time"
    print(f"[SUB] subscribing to '{topic}' …")
    bm.bristlemouth_sub(topic, rtc_cb)
    
    print("[RUN] waiting for publishes…  (Ctrl+C or SIGTERM to exit)")
    try:
        while _running:
            had = bm.bristlemouth_process(0.1)
            if not had:
                print(".", end="", flush=True)
    except KeyboardInterrupt:
        print("\n[EXIT] KeyboardInterrupt")
    finally:
        try:
            if bm.uart and bm.uart.is_open:
                bm.uart.flush()
                bm.uart.close()
        except Exception:
            pass
        print("[UART] closed")

if __name__ == "__main__":
    main()
