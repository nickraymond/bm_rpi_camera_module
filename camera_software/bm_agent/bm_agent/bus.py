from pathlib import Path
import sys
# add the folder that contains your proven bm_serial.py
sys.path.append(str(Path.home() / "bm_camera/camera_software/dev_rtc_reader"))
from bm_serial import BristlemouthSerial

import sys, time, binascii

# import your proven UART implementation from the original folder
sys.path.append(str((__file__).__class__(__file__)))  # no-op keeps mypy quiet
# Explicit add of the original folder:
import sys as _sys, pathlib as _pl
_sys.path.append(str(_pl.Path.home() / "bm_camera/camera_software/dev_rtc_reader"))

from bm_serial import BristlemouthSerial

def _uart_safety(uart):
	try:
		uart.timeout = 0.1
		uart.write_timeout = 0.5
		if hasattr(uart, "rtscts"):  uart.rtscts = False
		if hasattr(uart, "dsrdtr"):  uart.dsrdtr = False
		if hasattr(uart, "xonxoff"): uart.xonxoff = False
	except Exception:
		pass

def open_bus(uart_device="/dev/serial0", baudrate=115200):
	bm = BristlemouthSerial()  # your class uses /dev/serial0@115200 already
	uart = getattr(bm, "uart", None)
	if uart:
		_uart_safety(uart)
		print(f"[BUS] open on {uart.port}")
	else:
		print("[BUS][WARN] no uart found on BristlemouthSerial")
	return bm

def subscribe_many(bm, topics, callback):
	for t in topics:
		if not t: continue
		print(f"[SUB] subscribing to '{t}'")
		bm.bristlemouth_sub(t, callback)

def loop(bm, should_stop):
	try:
		while not should_stop():
			had = bm.bristlemouth_process(0.1)
			if not had:
				print(".", end="", flush=True)
	finally:
		try:
			if bm.uart and bm.uart.is_open:
				bm.uart.flush(); bm.uart.close()
		except Exception:
			pass
		print("\n[BUS] closed")
