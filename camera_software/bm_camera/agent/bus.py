# bm_agent/bm_agent/bus.py
import sys
import time
import serial  # needed for SerialException

from bm_serial import BristlemouthSerial

# bm_agent/bus.py
import bm_serial as _bm_serial
print(f"[BUS][DEBUG] bm_serial file: {_bm_serial.__file__}")
print(f"[BUS][DEBUG] has spotter_print: {hasattr(_bm_serial.BristlemouthSerial, 'spotter_print')}")



def _uart_safety(uart):
	"""Best-effort flush/reset so we start clean."""
	try:
		uart.reset_input_buffer()
		uart.reset_output_buffer()
	except Exception:
		pass


def open_bus(uart_device="/dev/serial0", baudrate=115200):
	"""
	Open BM UART using the configured device & baudrate.
	Prints clear hints if the port is busy or missing.
	"""
	try:
		bm = BristlemouthSerial(port=uart_device, baudrate=baudrate, timeout=0.5)
	except serial.SerialException as e:
		msg = str(e)
		if "exclusively lock port" in msg or "Resource temporarily unavailable" in msg:
			print(f"[BUS][ERROR] {uart_device} is busy (owned by another process).")
			print("  Hints:")
			print("   • stop services first:  sudo systemctl stop bm-camera-agent serial-getty@ttyS0")
			print(f"   • see current owner:    sudo lsof {uart_device}")
			print("   • then try again in the foreground")
			sys.exit(2)
		print(f"[BUS][ERR] could not open {uart_device} @ {baudrate}: {e}")
		raise

	uart = getattr(bm, "uart", None)
	if uart:
		_uart_safety(uart)
		print(f"[BUS] open on {uart.port}")
	else:
		print("[BUS][WARN] no uart found on BristlemouthSerial")
	return bm


def subscribe_many(bm: BristlemouthSerial, topics, cb):
	"""
	Subscribe one callback to many topics. Logs each subscription.
	"""
	for t in topics:
		topic = t if isinstance(t, str) else str(t)
		print(f"[SUB] subscribing to '{topic}'")
		bm.bristlemouth_sub(topic, cb)


def loop(bm: BristlemouthSerial, should_stop=None):
	"""
	Pump the serial bus until should_stop() returns True.
	Prints a heartbeat dot so you know we're alive.
	"""
	try:
		last_dot = 0.0
		while True:
			bm.bristlemouth_process(0.1)
			if should_stop and should_stop():
				break
			now = time.monotonic()
			if now - last_dot >= 1.0:
				# 1-sec heartbeat
				sys.stdout.write(".")
				sys.stdout.flush()
				last_dot = now
			time.sleep(0.05)
	finally:
		try:
			bm.uart.close()
		except Exception:
			pass
		print("\n[BUS] closed")
