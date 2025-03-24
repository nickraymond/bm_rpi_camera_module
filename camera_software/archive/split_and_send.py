
import cv2
import os
import shutil
import base64
import time
from bm_serial import BristlemouthSerial

buffer_size = 300
compression_quality = 10  # 15 recommended for manageable size buffers

def encode_to_base64(binary_data):
	base64_encoded_data = base64.b64encode(binary_data)
	return base64_encoded_data.decode('ascii')

def split(image):
	# Cleanup old buffers
	directory_path = '/home/pi/BM_Devel_Pi/buffers/'
	if os.path.exists(directory_path):
		shutil.rmtree(directory_path)
		print("Deleted buffers dir")
	# Create new buffers directory
	os.makedirs(directory_path, exist_ok=True)
	print("Created buffers dir")
	
	# Encode image to jpeg
	retval, buffer = cv2.imencode('.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), compression_quality])
	print(f"length of buffer: {len(buffer)}")

	if retval:
		# Convert buffer to a bytes object and encode in base64
		base64_data = base64.b64encode(buffer).decode("ascii")
		print(f"length of base 64: {len(base64_data)}")
		print("Success encoding image")
	else:
		raise ValueError("Failed to encode image")

	file_length = len(base64_data)

	buffer_number = 0
	while (buffer_number * buffer_size < file_length):
		start_pos = buffer_number * buffer_size
		current_buffer = base64_data[start_pos:start_pos + buffer_size]
	   # print(f"Saving buffer {buffer_number}, start_pos: {start_pos}")

		# Write the buffer to its own text file
		path = os.path.join(directory_path, f"split_{buffer_number}.txt")
		with open(path, 'w') as buffer_file:
			buffer_file.write(current_buffer)
		
		buffer_number += 1

	print(f"Saved {buffer_number} buffer txt files.")

def send():
	# Find the number of buffer files generated
	directory_path = '/home/pi/BM_Devel_Pi/buffers/'
	if os.path.exists(directory_path):
		# List everything in the directory
		files = os.listdir(directory_path)
		num_buffers = len(files)
		print(f"{num_buffers} buffers found")

	# Get the index label for this image
	capture_directory_path = '/home/pi/BM_Devel_Pi/capture_archive/'
	if os.path.exists(capture_directory_path):
		# List everything in the directory
		files = os.listdir(capture_directory_path)
		this_capture_index = len(files) - 1
		print(f"Working with image index {this_capture_index}")

	# Initialize the BristlemouthSerial object
	bm = BristlemouthSerial()

	try:
		start_msg = f"<START IMG {this_capture_index}> length: {num_buffers}\n"
		bm.spotter_tx(start_msg.encode('ascii'))
		print(f'Sent {start_msg}')
		time.sleep(5)  # wait to ensure the start tag sends fully

		for i in range(num_buffers):
			buffer_path = os.path.join(directory_path, f"split_{i}.txt")
			with open(buffer_path, 'r') as buffer_file:
				buffer_data = buffer_file.read()
			buffer_to_send = f"<I{i}>" + buffer_data + '\n'
			bm.spotter_tx(buffer_to_send.encode('ascii'))
			print(f'Sent buffer {i} of {num_buffers}')
			time.sleep(5)

		time.sleep(10)  # wait to ensure all send before the end tag
		end_msg = f"<END IMG {this_capture_index}>\n"
		bm.spotter_tx(end_msg.encode('ascii'))
		print(f'Sent {end_msg}')
	except Exception as e:
		print("An exception occurred:", e)
	finally:
		bm.uart.close()

def send_message(msg):
	# Initialize the BristlemouthSerial object
	bm = BristlemouthSerial()
	try:
		bm.spotter_tx(msg.encode('ascii'))
		print(f"Sent: {msg}")
		
	except Exception as e:
		print("An exception occurred:", e)
	finally:
		bm.uart.close()

if __name__ == "__main__":
	img = cv2.imread("/home/pi/BM_Devel_Pi/capture_archive/image_VGA.jpg")
	if img is None:
		raise ValueError("Image is empty or not loaded correctly")
	split(img)
	send()
