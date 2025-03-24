
from bm_serial import BristlemouthSerial
import board
import digitalio
import time

#led = digitalio.DigitalInOut(board.LED)
#led.direction = digitalio.Direction.OUTPUT
bm = BristlemouthSerial()
last_send = time.time()
print("starting the test...")

while True:
	now = time.time()
	if now - last_send > 15:
		#led.value = True
		last_send = now
		print("publishing", now)
		bm.spotter_tx(b"sensor1: 1234.56, binary_ok_too: \x00\x01\x02\x03\xff\xfe\xfd")
		bm.spotter_log(
			"any_file_name.log",
			"Sensor 1: 1234.99. More detailed human-readable info for the SD card logs.",
		)
		#led.value = False
