# import serial
# import serial.tools.list_ports
# 
# def check_uart(port_name):
# 	try:
# 		# Try to open the port
# 		ser = serial.Serial(port_name, baudrate=9600, timeout=1)
# 		
# 		if ser.is_open:
# 			print(f"{port_name} is open and working!")
# 			# Optionally write and read to test
# 			ser.write(b"Test")
# 			response = ser.read(10)  # Try to read something back (optional)
# 			if response:
# 				print(f"Received data: {response}")
# 			ser.close()  # Close the port
# 			return True
# 		else:
# 			print(f"{port_name} is not working.")
# 			return False
# 	except (serial.SerialException, OSError) as e:
# 		print(f"Error: {e}")
# 		return False
# 
# # Specify the UART port to check
# #uart_port = "/dev/ttyAMA0"  # Change this to your specific UART port
# uart_port = "/dev/serial1"  # Change this to your specific UART port
# 
# 
# # Run the check
# if check_uart(uart_port):
# 	print(f"{uart_port} is functioning properly.")
# else:
# 	print(f"{uart_port} is not available or not working.")
import serial
import time

def test_uart(port):
	try:
		ser = serial.Serial(port, 115200, timeout=1)
		ser.flush()

		test_data = "Raspberry Pi says hello"
		ser.write(test_data.encode('utf-8'))
		time.sleep(0.1)  # Give some time for the data to be transmitted
		if ser.in_waiting > 0:
			response = ser.read(ser.in_waiting).decode('utf-8')
			print(f"Received on {port}: {response}")
		else:
			print(f"No response on {port}")
		ser.close()
	except serial.SerialException as e:
		print(f"Error on {port}: {e}")

test_uart('/dev/serial0')
test_uart('/dev/serial1')
test_uart('/dev/ttyS0')
test_uart('/dev/ttyAMA0')
