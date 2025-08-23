# filename: process_image.py
# description: control the quality of image, compression, splitting file into smaller chunks, and filename when saving
#
# Copyright 2025 Nick Raymond
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import cv2
import os
import csv
import shutil
import base64
import time
from datetime import datetime, timezone
from picamera2 import Picamera2
import subprocess  # Fix for missing import
from bm_serial import BristlemouthSerial
from PIL import Image
import pillow_heif  # Add HEIC support

# Register HEIF/HEIC support
pillow_heif.register_heif_opener()

# # Setup the Bristlemouth UART Serial
# bm = BristlemouthSerial()

# Setup the Bristlemouth UART Serial (replaced the above)
try:
	from bm_serial import BristlemouthSerial
	bm = BristlemouthSerial()
except Exception:
	bm = None  # running inside bm_agent (UART already in use) or UART unavailable
	
# Define the UART buffer size for BM serial coms
BUFFER_SIZE = 300

# Debug flag to control printing of messages to the terminal
DEBUG = True

# # Hard-coded image directory path
# IMAGE_DIRECTORY = "/home/pi/BM_Devel_Pi/images"
# BUFFER_DIRECTORY = "/home/pi/BM_Devel_Pi/buffer"
# LOG_FILE = "/home/pi/BM_Devel_Pi/camera_log.csv"

# Determine the base directory where the current script is located.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Create file paths relative to the base directory.
IMAGE_DIRECTORY = os.path.join(BASE_DIR, "images")
BUFFER_DIRECTORY = os.path.join(BASE_DIR, "buffer")
LOG_FILE = os.path.join(BASE_DIR, "camera_log.csv")

# Ensure the directories exist
os.makedirs(IMAGE_DIRECTORY, exist_ok=True)
os.makedirs(BUFFER_DIRECTORY, exist_ok=True)

# Define the image quality and compression values
COMPRESSION_QUALITY = 25  # Adjust this value as needed (e.g., 25, 50, 75)
RESOLUTION_KEY = "VGA"  # Adjust this value as needed "720p", "1080p"...



# Define the available resolution options
RESOLUTIONS = {
	"12MP": (4056, 3040),
	"8MP": (3264, 2448),
	"5MP": (2592, 1944),
	"4MP": (2464, 1848),
	"1080p": (1920, 1080),
	"720p": (1280, 720),
	"VGA": (640, 480)
}

def debug_print(message):
	"""Helper function to print debug messages if debugging is enabled."""
	if DEBUG:
		print(f"[DEBUG] {message}")
		
		# Save message to Spotter SD card
		bm.spotter_log("camera_module.log", message)
		

def validate_resolution(resolution_key):
	"""Validate the resolution key and return the corresponding resolution."""
	if resolution_key not in RESOLUTIONS:
		raise ValueError(f"Invalid resolution key. Choose from: {', '.join(RESOLUTIONS.keys())}")
	return RESOLUTIONS[resolution_key]


def generate_filename():
	"""Generate a filename in the format of ISO 8601 timestamp + image.jpg."""
	current_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
	return f"{current_timestamp}_image.jpg"


def capture_image(resolution_key="VGA", directory_path=IMAGE_DIRECTORY):
	"""Capture an image with the specified resolution and save it in the directory."""
	resolution = validate_resolution(resolution_key)

	# Initialize the camera
	picam2 = Picamera2()

	# Set the configuration with the chosen resolution
	config = picam2.create_still_configuration(main={"size": resolution})

	# Apply the configuration
	picam2.configure(config)

	# Start the camera
	picam2.start()

	# Allow the camera to warm up
	time.sleep(2)

	# Generate the filename and construct the full image path
	image_filename = generate_filename()
	image_path = os.path.join(directory_path, image_filename)

	# Ensure the directory exists
	if not os.path.exists(directory_path):
		os.makedirs(directory_path)

	# Capture the image and save it to the specified path
	picam2.capture_file(image_path)
	
	# Get the file size in bytes
	file_size = os.path.getsize(image_path)
	
	# Update the debug print statement to include the file size
	debug_print(f"Image saved as '{image_path}', file size = {file_size} bytes")

	#debug_print(f"Raw image saved as '{image_path}'")

	# Stop the camera
	picam2.stop()

	return image_path  # Return the path for further use


def encode_to_base64(binary_data):
	return base64.b64encode(binary_data).decode('ascii')


def get_cpu_temperature():
	"""Get the Raspberry Pi's CPU temperature."""
	result = subprocess.run(["vcgencmd", "measure_temp"], capture_output=True, text=True)
	temp_str = result.stdout.strip().replace("temp=", "").replace("'C", "")
	return float(temp_str)


def get_file_size(file_path):
	"""Get the file size of a given file in bytes."""
	if os.path.exists(file_path):
		return os.path.getsize(file_path)
	return 0


def split_image_jpeg(image_path, buffer_directory, compression_quality):
	"""Splits the image into base64-encoded buffers."""
	if os.path.exists(buffer_directory):
		shutil.rmtree(buffer_directory)
		debug_print("Deleted buffers dir")

	os.makedirs(buffer_directory, exist_ok=True)
	debug_print("Created buffers dir")

	image = cv2.imread(image_path)
	
	# Check if the image was loaded successfully
	if image is None:
		raise ValueError(f"Failed to load image from path: {image_path}")
	
	# Compress the image to JPEG format
	retval, buffer = cv2.imencode('.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), compression_quality])
	if not retval:
		raise ValueError("Failed to encode image")

	if not retval:
		raise ValueError("Failed to encode image")

	# Save the compressed image with "_compressed" appended to the filename
	file_dir, file_name = os.path.split(image_path)
	file_name_no_ext, file_ext = os.path.splitext(file_name)
	compressed_file_path = os.path.join(file_dir, f"{file_name_no_ext}_compressed{file_ext}")
	
	# Write the compressed image back to the same directory
	with open(compressed_file_path, 'wb') as compressed_file:
		compressed_file.write(buffer)
	
	debug_print(f"Compressed image saved as: {compressed_file_path}")

	base64_data = base64.b64encode(buffer).decode("ascii")
	file_length = len(base64_data)

	buffer_number = 0
	while buffer_number * BUFFER_SIZE < file_length:
		start_pos = buffer_number * BUFFER_SIZE
		current_buffer = base64_data[start_pos:start_pos + BUFFER_SIZE]
		buffer_path = os.path.join(buffer_directory, f"split_{buffer_number}.txt")
		with open(buffer_path, 'w') as buffer_file:
			buffer_file.write(current_buffer)
		buffer_number += 1

	debug_print(f"Saved {buffer_number} buffer txt files.")


def split_image_heic(image_path, compression_quality=25):
	"""Compress the image to HEIC and split into buffers."""
	if os.path.exists(BUFFER_DIRECTORY):
		shutil.rmtree(BUFFER_DIRECTORY)
		debug_print("Deleted buffers directory")
	
	os.makedirs(BUFFER_DIRECTORY, exist_ok=True)
	debug_print("Created buffers directory")
	
	# Generate the HEIC output path in IMAGE_DIRECTORY
	file_name_without_ext = os.path.splitext(os.path.basename(image_path))[0]
	heic_output_path = os.path.join(IMAGE_DIRECTORY, f"{file_name_without_ext}_compressed.heic")
	
	# Open the image and save it as HEIC
	with Image.open(image_path) as img:
		img.save(heic_output_path, format="HEIF", quality=compression_quality)
	
	# Get the file size in bytes
	file_size = os.path.getsize(heic_output_path)
	
	# Update the debug print statement to include the file size
	debug_print(f"Compressed image saved as '{heic_output_path}', file size = {file_size} bytes")

	# Read the compressed HEIC file as binary
	with open(heic_output_path, "rb") as heic_file:
		heic_data = heic_file.read()
	
	# Encode the HEIC data into Base64
	base64_data = base64.b64encode(heic_data).decode("ascii")
	file_length = len(base64_data)
	
	# Split Base64 data into buffers and save in BUFFER_DIRECTORY
	buffer_number = 0
	while buffer_number * BUFFER_SIZE < file_length:
		start_pos = buffer_number * BUFFER_SIZE
		current_buffer = base64_data[start_pos:start_pos + BUFFER_SIZE]
		buffer_path = os.path.join(BUFFER_DIRECTORY, f"split_{buffer_number}.txt")
		with open(buffer_path, 'w') as buffer_file:
			buffer_file.write(current_buffer)
		buffer_number += 1
	
	debug_print(f"Saved {buffer_number} buffer text files in {BUFFER_DIRECTORY}")
	
	return os.path.basename(heic_output_path), buffer_number, len(heic_data)


def send_buffers(buffer_directory, compressed_file_name):
		"""Send the buffer files over UART."""
		files = os.listdir(buffer_directory)
		num_buffers = len(files)
		
		if num_buffers == 0:
			raise ValueError("No buffers found to send!")
		
		# Moved to top of module so that debug_print() can use it 
		# bm = BristlemouthSerial()
		current_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
		
		debug_print(f"Starting transmission of image: {compressed_file_name} with {num_buffers} buffers.")
		
		# Construct the start message
		start_msg = (
			f"<START IMG> filename: {compressed_file_name}, "
			f"timestamp: {current_timestamp}, length: {num_buffers}\n"
		)
		bm.spotter_tx(start_msg.encode('ascii'))
		time.sleep(5)
		
		# Transmit each buffer
		for i in range(num_buffers):
			buffer_path = os.path.join(buffer_directory, f"split_{i}.txt")
			with open(buffer_path, 'r') as buffer_file:
				buffer_data = buffer_file.read()
			buffer_to_send = f"<I{i}>{buffer_data}\n"
			bm.spotter_tx(buffer_to_send.encode('ascii'))
			debug_print(f"Sent buffer {i+1} of {num_buffers}")
			time.sleep(5)
		
		# Send the end message
		end_msg = f"<END IMG>\n"
		bm.spotter_tx(end_msg.encode('ascii'))
		debug_print(f"Finished transmission of image: {compressed_file_name}")
		#bm.uart.close()


def compress_and_send_image(image_path, compression_quality=25):
	"""Compress the image to HEIC, save it, and send buffers."""
	# Compress the image and get details
	compressed_file_name, num_buffers, file_size_compressed = split_image_heic(
		image_path, compression_quality=compression_quality
	)
	
	# Send buffers
	send_buffers(BUFFER_DIRECTORY, compressed_file_name)
	
	return compressed_file_name, num_buffers, file_size_compressed

def log_message(
		rtc_time, compressed_image_filename, file_size_raw, file_size_compressed,
		compression_quality, num_buffers, execution_time, within_window, cpu_temp
	):
		"""
		Log details to the CSV file and print a concise log message to the terminal.
		"""
		# Check if the log file exists to write the header if necessary
		file_exists = os.path.isfile(LOG_FILE)
	
		with open(LOG_FILE, 'a', newline='') as file:
			writer = csv.writer(file)
	
			# Write the header if the local CSV file does not exist 
			if not file_exists:
				writer.writerow([
					"RTC Timestamp (UTC)", "Compressed Image Filename", "Raw File Size (bytes)",
					"Compressed File Size (bytes)", "Compression Quality", "Number of Buffers",
					"Execution Time (minutes)", "Within Time Window", "CPU Temp (°C)"
				])
	
			# Log message content for local CSV file
			writer.writerow([
				rtc_time.strftime('%Y-%m-%dT%H:%M:%SZ'), compressed_image_filename, file_size_raw,
				file_size_compressed, COMPRESSION_QUALITY, num_buffers, 
				f"{execution_time:.2f}", within_window, f"{cpu_temp:.2f}"
			])
	
			# # Build concise log message for terminal output
			# log_msg = (
			# 	f"RTC: {rtc_time.strftime('%Y-%m-%dT%H:%M:%SZ')}, "
			# 	f"File: {compressed_image_filename}, "
			# 	f"Raw Size: {file_size_raw} bytes, Compressed Size: {file_size_compressed} bytes, "
			# 	f"Quality: {COMPRESSION_QUALITY}, Buffers: {num_buffers}, "
			# 	f"Execution Time: {execution_time:.2f} min, Within Window: {within_window}, "
			# 	f"CPU Temp: {cpu_temp:.2f}°C"
			# )
			# 
			# # Print log message to the terminal
			# print(log_msg)
			
			# Build concise log message for terminal output
			
			#debug_print(f"RTC: {rtc_time.strftime('%Y-%m-%dT%H:%M:%SZ')}")
			#time.sleep(1)
			#debug_print(f"File: {compressed_image_filename}")
			debug_print(f"Raw image size: {file_size_raw} bytes")
			debug_print(f"Quality: {COMPRESSION_QUALITY}")
			debug_print(f"Compressed image size: {file_size_compressed} bytes")
			debug_print(f"Buffers: {num_buffers}")
			debug_print(f"Execution Time: {execution_time:.2f} min")
			debug_print(f"Within Window: {within_window}")
			debug_print(f"CPU Temp: {cpu_temp:.2f}°C")
			debug_print(" ")
			debug_print(" ")
			debug_print(" ")

			

def close_bm_serial():
	"""Close the BM serial once complete"""
	bm.uart.close()
	return 0
		
	

