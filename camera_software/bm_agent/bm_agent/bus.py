# bm_agent/bm_agent/bus.py
from __future__ import annotations
import os
import sys
import time
from pathlib import Path
from typing import Callable, Iterable, Any

# --- import your known-good BristlemouthSerial helper once, cleanly ---
DEV_HELPER = Path.home() / "bm_camera/camera_software/dev_rtc_reader"
if str(DEV_HELPER) not in sys.path:
	sys.path.append(str(DEV_HELPER))

from bm_serial import BristlemouthSerial  # provides .uart, .bristlemouth_sub(), .bristlemouth_process()

try:
	import serial  # for type/timeout controls and exceptions
except Exception:
	serial = None  # still works; we just won't tweak timeouts explicitly


# --- small UART hygiene helpers ---

def _uart_safety(uart) -> None:
	"""Set sane defaults: bounded timeouts, no flow control."""
	try:
		# a little time for reads; and a generous write timeout so we don't insta-fail
		if getattr(uart, "timeout", None) in (None, 0):
			uart.timeout = 0.2
		if hasattr(uart, "write_timeout"):
			uart.write_timeout = 3.0  # was 0.5; lengthen to ride out slow peer startup

		# disable HW/SW flow control unless you KNOW you need them
		if hasattr(uart, "rtscts"):
			uart.rtscts = False
		if hasattr(uart, "dsrdtr"):
			uart.dsrdtr = False
		if hasattr(uart, "xonxoff"):
			uart.xonxoff = False
	except Exception:
		pass

def _settle(uart) -> None:
	"""Clear buffers and give the peer a breath."""
	try:
		uart.reset_input_buffer()
	except Exception:
		pass
	try:
		uart.reset_output_buffer()
	except Exception:
		pass
	time.sleep(0.05)


# --- public API used by run_agent.py ---

def open_bus(uart_device: str = "/dev/serial0", baudrate: int = 115200) -> BristlemouthSerial:
	"""
	Create your BristlemouthSerial wrapper. Your helper typically opens /dev/serial0 internally.
	We don't fight that—just configure and log clearly.
	"""
	# Most versions of your helper take no args and open /dev/serial0@115200 by default.
	bm = BristlemouthSerial()

	uart = getattr(bm, "uart", None)
	if uart:
		_uart_safety(uart)
		real = os.path.realpath(uart.port)
		print(f"[BUS] open port={uart.port} (real={real}) baud={getattr(uart, 'baudrate', baudrate)}")
		_settle(uart)
	else:
		print("[BUS][WARN] BristlemouthSerial.uart missing")

	return bm


def subscribe_one(bm: BristlemouthSerial, topic: str,
				  callback: Callable[[int, str, bytes], Any]) -> None:
	"""Subscribe to exactly one topic (back-to-basics)."""
	if not topic:
		return
	print(f"[SUB(req)] {topic!r}")
	# NOTE: bm_serial may also print its own "[SUB]" line; that's expected.
	bm.bristlemouth_sub(topic, callback)


def subscribe_many(bm: BristlemouthSerial, topics: Iterable[str],
				   callback: Callable[[int, str, bytes], Any]) -> None:
	"""
	Retained for compatibility, but just fans out to subscribe_one().
	Not the cause of your timeouts; the actual UART write happens inside bristlemouth_sub().
	"""
	for t in topics:
		if t:
			subscribe_one(bm, t, callback)


def loop(bm: BristlemouthSerial, should_stop) -> None:
	"""
	Drive the Bristlemouth reader. Always closes the port before returning.
	"""
	try:
		while not should_stop():
			bm.bristlemouth_process(0.1)
	finally:
		try:
			print("[BUS] closing…")
			if getattr(bm, "uart", None) and bm.uart.is_open:
				try:
					bm.uart.flush()
				except Exception:
					pass
				bm.uart.close()
		finally:
			print("[BUS] closed")
