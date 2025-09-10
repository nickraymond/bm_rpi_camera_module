# # bm_camera/agent/bus.py
# import logging
# import sys
# import time
# import serial  # SerialException
# 
# from datetime import datetime, timezone
# from bm_camera.io.bm_serial import BristlemouthSerial
# 
# logger = logging.getLogger("BUS")
# 
# 
# def _uart_safety(uart):
# 	"""Best-effort flush/reset so we start clean."""
# 	try:
# 		uart.reset_input_buffer()
# 		uart.reset_output_buffer()
# 	except Exception:
# 		pass
# 
# 
# def open_bus(uart_device="/dev/serial0", baudrate=115200):
# 	"""
# 	Open BM UART using the configured device & baudrate.
# 	"""
# 	try:
# 		bm = BristlemouthSerial(port=uart_device, baudrate=baudrate, timeout=0.5)
# 	except serial.SerialException as e:
# 		msg = str(e)
# 		if "exclusively lock port" in msg or "Resource temporarily unavailable" in msg:
# 			logger.error("%s is busy (owned by another process).", uart_device)
# 			logger.info("Hints:")
# 			logger.info(" • stop services first:  sudo systemctl stop bm-camera-agent serial-getty@ttyS0")
# 			logger.info(" • see current owner:    sudo lsof %s", uart_device)
# 			sys.exit(2)
# 		logger.error("could not open %s @ %s: %s", uart_device, baudrate, e)
# 		raise
# 
# 	uart = getattr(bm, "uart", None)
# 	if uart:
# 		_uart_safety(uart)
# 		logger.info("[BUS] open on %s", uart.port)
# 	else:
# 		logger.warning("[BUS][WARN] no uart found on BristlemouthSerial")
# 	return bm
# 
# 
# def subscribe_many(bm: BristlemouthSerial, topics, cb):
# 	"""Subscribe one callback to many topics. Logs each subscription."""
# 	for t in topics:
# 		topic = t if isinstance(t, str) else str(t)
# 		logger.info("[SUB] subscribing to '%s'", topic)
# 		bm.bristlemouth_sub(topic, cb)
# 
# 
# # def loop(bm: BristlemouthSerial, should_stop=None):
# # 	"""Pump the serial bus until should_stop() returns True."""
# # 	# try:
# # 	# 	last_dot = 0.0
# # 	# 	while True:
# # 	# 		bm.bristlemouth_process(0.1)
# # 	# 		if should_stop and should_stop():
# # 	# 			break
# # 	# 		now = time.monotonic()
# # 	# 		if now - last_dot >= 1.0:
# # 	# 			sys.stdout.write(".")
# # 	# 			sys.stdout.flush()
# # 	# 			last_dot = now
# # 	# 		time.sleep(0.05)
# def loop(bm: BristlemouthSerial, should_stop=None):
# 	logger = logging.getLogger("BUS")
# 	try:
# 		last_hb = 0.0
# 		while True:
# 			bm.bristlemouth_process(0.1)
# 			if should_stop and should_stop():
# 				break
# 			now = time.monotonic()
# 			if now - last_hb >= 5.0:
# 				logger.debug("[HB] bus alive")
# 				last_hb = now
# 			time.sleep(0.05)
# 
# 	finally:
# 		try:
# 			bm.uart.close()
# 		except Exception:
# 			pass
# 		print("\n[BUS] closed")
# bm_camera/agent/bus.py
import logging
import sys
import time
import serial  # SerialException
from datetime import datetime, timezone

from bm_camera.io.bm_serial import BristlemouthSerial

log = logging.getLogger("BUS")


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
	"""
	try:
		bm = BristlemouthSerial(port=uart_device, baudrate=baudrate, timeout=0.5)
	except serial.SerialException as e:
		msg = str(e)
		if "exclusively lock port" in msg or "Resource temporarily unavailable" in msg:
			log.error("%s is busy (owned by another process).", uart_device)
			log.info("Hints:")
			log.info(" • stop services first:  sudo systemctl stop bm-camera-agent serial-getty@ttyS0")
			log.info(" • see current owner:    sudo lsof %s", uart_device)
			sys.exit(2)
		log.error("could not open %s @ %s: %s", uart_device, baudrate, e)
		raise

	uart = getattr(bm, "uart", None)
	if uart:
		_uart_safety(uart)
		log.info("[BUS] open on %s", uart.port)
	else:
		log.warning("[BUS][WARN] no uart found on BristlemouthSerial")
	return bm


def subscribe_many(bm: BristlemouthSerial, topics, cb):
	"""Subscribe one callback to many topics. Logs each subscription."""
	for t in topics:
		topic = t if isinstance(t, str) else str(t)
		log.info("[SUB] subscribing to '%s'", topic)
		bm.bristlemouth_sub(topic, cb)


def loop(bm: BristlemouthSerial, should_stop=None):
	"""Pump the serial bus until should_stop() returns True."""
	try:
		last_hb = 0.0
		while True:
			bm.bristlemouth_process(0.1)
			if should_stop and should_stop():
				break
			now = time.monotonic()
			if now - last_hb >= 1.0:
				# Heartbeat at DEBUG, matches overall log style
				iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
				log.debug("[HB] %s alive", iso)
				last_hb = now
			time.sleep(0.05)
	finally:
		try:
			bm.uart.close()
		except Exception:
			pass
		log.info("[BUS] closed")
