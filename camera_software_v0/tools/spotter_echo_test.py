#!/usr/bin/env python3
import sys, time
from pathlib import Path

PROJECT = Path.home() / "bm_camera" / "camera_software"
sys.path.insert(0, str(PROJECT))
from bm_serial import BristlemouthSerial

def main():
	try:
		bm = BristlemouthSerial()
	except Exception as e:
		print(f"[TEST][ERR] open UART: {e!r}")
		sys.exit(1)
	try:
		bm.spotter_print("HELLO from Pi (spotter_print test)")
		time.sleep(0.5)
		for i in range(3, 0, -1):
			bm.spotter_print(f"countdown {i}")
			time.sleep(0.5)
		bm.spotter_print("OK done")
		print("[TEST] sent 5 lines to spotter/printf")
	finally:
		try:
			bm.uart.close()
		except Exception:
			pass

if __name__ == "__main__":
	main()
