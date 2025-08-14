# import serial
# 
# class BristlemouthSerial:
# 	def __init__(self, uart=None, node_id=0xC0FFEEEEF0CACC1A):
# 		self.node_id = node_id
# 		if uart is None:
# 			self.uart = serial.Serial('/dev/ttyAMA0', 115200)  # Adjust the serial port, ttyAMA0 as needed, ttyS0
# 		else:
# 			self.uart = uart
# 
# 	def spotter_tx(self, data):
# 		topic = b"spotter/transmit-data"
# 		packet = (
# 			self.get_pub_header()
# 			+ len(topic).to_bytes(2, "little")
# 			+ topic
# 			+ b"\x01"
# 			+ data
# 		)
# 		cobs = self.finalize_packet(packet)
# 		return self.uart.write(cobs)
# 
# 	def spotter_log(self, filename, data):
# 		topic = b"spotter/fprintf"
# 		packet = (
# 			self.get_pub_header()
# 			+ len(topic).to_bytes(2, "little")
# 			+ topic
# 			+ b"\x00" * 8
# 			+ len(filename).to_bytes(2, "little")
# 			+ (len(data) + 1).to_bytes(2, "little")
# 			+ filename.encode()
# 			+ data.encode()
# 			+ b"\n"
# 		)
# 		cobs = self.finalize_packet(packet)
# 		return self.uart.write(cobs)
# 
# 	def finalize_packet(self, packet):
# 		checksum = self.crc(0, packet)
# 		packet[2] = checksum & 0xFF
# 		packet[3] = (checksum >> 8) & 0xFF
# 		cobs = self.cobs_encode(packet) + b"\x00"
# 		return cobs
# 
# 	def get_pub_header(self):
# 		return (
# 			bytearray.fromhex("02000000")
# 			+ self.node_id.to_bytes(8, "little")
# 			+ bytearray.fromhex("0101")
# 		)
# 
# 	def cobs_encode(self, in_bytes):
# 		final_zero = True
# 		out_bytes = bytearray()
# 		idx = 0
# 		search_start_idx = 0
# 		for in_char in in_bytes:
# 			if in_char == 0:
# 				final_zero = True
# 				out_bytes.append(idx - search_start_idx + 1)
# 				out_bytes += in_bytes[search_start_idx:idx]
# 				search_start_idx = idx + 1
# 			else:
# 				if idx - search_start_idx == 0xFD:
# 					final_zero = False
# 					out_bytes.append(0xFF)
# 					out_bytes += in_bytes[search_start_idx : idx + 1]
# 					search_start_idx = idx + 1
# 			idx += 1
# 		if idx != search_start_idx or final_zero:
# 			out_bytes.append(idx - search_start_idx + 1)
# 			out_bytes += in_bytes[search_start_idx:idx]
# 		return bytes(out_bytes)
# 
# 	def crc(self, seed, src):
# 		e, f = 0, 0
# 		for i in src:
# 			e = (seed ^ i) & 0xFF
# 			f = e ^ ((e << 4) & 0xFF)
# 			seed = (seed >> 8) ^ (((f << 8) & 0xFFFF) ^ ((f << 3) & 0xFFFF)) ^ (f >> 4)
# 		return seed
# 
# 	def deinit(self):
# 		if self.uart:
# 			self.uart.close()
# 			self.uart = None
# updated code to remove the "|" type hinting symbol, since not supported in python3.9
# Changes Made:
# Replaced int | None with Optional[int] from the typing module.
# Added Optional and Union imports from the typing module.
# Encoded filename and data to bytes in the spotter_log method to ensure proper handling.
# Switch to pyserial for UART communication for RPi

import serial

class BristlemouthSerial:

	def __init__(self, uart=None, node_id=0xC0FFEEEEF0CACC1A):
		self.node_id = node_id
		if uart is None:
			self.uart = serial.Serial('/dev/ttyS0', 115200)  # Adjust the serial port as needed
			#self.uart = serial.Serial('/dev/ttyS0', 9600)  # Adjust the serial port as needed

		else:
			self.uart = uart

	def spotter_tx(self, data):
		topic = b"spotter/transmit-data"
		packet = (
			self.get_pub_header()
			+ len(topic).to_bytes(2, "little")
			+ topic
			+ b"\x01"
			+ data
		)
		cobs = self.finalize_packet(packet)
		return self.uart.write(cobs)

	def spotter_log(self, filename, data):
		topic = b"spotter/fprintf"
		packet = (
			self.get_pub_header()
			+ len(topic).to_bytes(2, "little")
			+ topic
			+ b"\x00" * 8
			+ len(filename).to_bytes(2, "little")
			+ (len(data) + 1).to_bytes(2, "little")
			+ filename.encode()
			+ data.encode()
			+ b"\n"
		)
		cobs = self.finalize_packet(packet)
		return self.uart.write(cobs)

	def finalize_packet(self, packet):
		checksum = self.crc(0, packet)
		packet[2] = checksum & 0xFF
		packet[3] = (checksum >> 8) & 0xFF
		cobs = self.cobs_encode(packet) + b"\x00"
		return cobs

	def get_pub_header(self):
		return (
			bytearray.fromhex("02000000")
			+ self.node_id.to_bytes(8, "little")
			+ bytearray.fromhex("0101")
		)

	def cobs_encode(self, in_bytes):
		final_zero = True
		out_bytes = bytearray()
		idx = 0
		search_start_idx = 0
		for in_char in in_bytes:
			if in_char == 0:
				final_zero = True
				out_bytes.append(idx - search_start_idx + 1)
				out_bytes += in_bytes[search_start_idx:idx]
				search_start_idx = idx + 1
			else:
				if idx - search_start_idx == 0xFD:
					final_zero = False
					out_bytes.append(0xFF)
					out_bytes += in_bytes[search_start_idx : idx + 1]
					search_start_idx = idx + 1
			idx += 1
		if idx != search_start_idx or final_zero:
			out_bytes.append(idx - search_start_idx + 1)
			out_bytes += in_bytes[search_start_idx:idx]
		return bytes(out_bytes)

	def crc(self, seed, src):
		e, f = 0, 0
		for i in src:
			e = (seed ^ i) & 0xFF
			f = e ^ ((e << 4) & 0xFF)
			seed = (seed >> 8) ^ (((f << 8) & 0xFFFF) ^ ((f << 3) & 0xFFFF)) ^ (f >> 4)
		return seed
