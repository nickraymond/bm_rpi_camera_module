	
# filename: image_capture.py
# description: control the quality of image, compression, splitting file into smaller chunks, and filename when saving

import cv2
import os
import csv
import shutil
import base64
import time
from datetime import datetime, timezone
from picamera2 import Picamera2
import subprocess
from PIL import Image
import pillow_heif  # Add HEIC support
from pathlib import Path

from bm_camera.common.paths import image_dir, buffer_dir
from bm_camera.common.config import get_resolutions
from bm_camera.common.config import resolve_resolution, get_camera_defaults


# Do not open UART from this module (agent owns it)
bm = None  # placeholder so guards like `if bm:` are safe


# Register HEIF/HEIC support
pillow_heif.register_heif_opener()

# Define the UART buffer size for BM serial coms
BUFFER_SIZE = 300

# Debug flag to control printing of messages to the terminal
DEBUG = True

HERE = Path(__file__).resolve().parent
IMAGE_DIRECTORY = image_dir()
BUFFER_DIRECTORY = buffer_dir()
LOG_FILE = str(HERE / "camera_log.csv")

# Ensure the directories exist
os.makedirs(IMAGE_DIRECTORY, exist_ok=True)
os.makedirs(BUFFER_DIRECTORY, exist_ok=True)

def debug_print(message: str):
	print(f"[DEBUG] {message}")
	try:
		with open(HERE / "camera_debug.log", "a") as f:
			f.write(message + "\n")
	except Exception:
		pass

# Define the image quality and compression values
COMPRESSION_QUALITY = 25  # Adjust this value as needed
RESOLUTION_KEY = "VGA"    # Default resolution

def validate_resolution(resolution_key):
	return resolve_resolution(resolution_key)

def generate_filename():
	"""Generate a filename in the format of ISO 8601 timestamp + image.jpg (UTC)."""
	current_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
	return f"{current_timestamp}_image.jpg"

def capture_image(resolution_key="VGA", directory_path=IMAGE_DIRECTORY):
	"""Capture an image with the specified resolution and save it in the directory."""
	#resolution = validate_resolution(resolution_key)
	resolution = resolve_resolution(resolution_key)
	picam2 = Picamera2()
	try:
		config = picam2.create_still_configuration(main={"size": resolution, "format": "BGR888"})
		picam2.configure(config)
		picam2.start()
		time.sleep(0.5)  # small warm-up

		image_filename = generate_filename()
		image_path = os.path.join(directory_path, image_filename)
		os.makedirs(directory_path, exist_ok=True)

		picam2.capture_file(image_path)

		file_size = os.path.getsize(image_path)
		debug_print(f"Image saved as '{image_path}', file size = {file_size} bytes")
		return image_path
	finally:
		# Ensure full release even on error
		try:
			picam2.stop()
		except Exception:
			pass
		try:
			picam2.close()
		except Exception:
			pass
		time.sleep(0.05)

def encode_to_base64(binary_data):
	return base64.b64encode(binary_data).decode('ascii')

def get_cpu_temperature():
	"""Get the Raspberry Pi's CPU temperature."""
	result = subprocess.run(["vcgencmd", "measure_temp"], capture_output=True, text=True)
	temp_str = result.stdout.strip().replace("temp=", "").replace("'C", "")
	try:
		return float(temp_str)
	except Exception:
		return float("nan")

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
	if image is None:
		raise ValueError(f"Failed to load image from path: {image_path}")

	retval, buffer = cv2.imencode('.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), compression_quality])
	if not retval:
		raise ValueError("Failed to encode image")

	file_dir, file_name = os.path.split(image_path)
	file_name_no_ext, file_ext = os.path.splitext(file_name)
	compressed_file_path = os.path.join(file_dir, f"{file_name_no_ext}_compressed{file_ext}")
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

	file_name_without_ext = os.path.splitext(os.path.basename(image_path))[0]
	heic_output_path = os.path.join(IMAGE_DIRECTORY, f"{file_name_without_ext}_compressed.heic")

	with Image.open(image_path) as img:
		img.save(heic_output_path, format="HEIF", quality=compression_quality)

	file_size = os.path.getsize(heic_output_path)
	debug_print(f"Compressed image saved as '{heic_output_path}', file size = {file_size} bytes")

	with open(heic_output_path, "rb") as heic_file:
		heic_data = heic_file.read()

	base64_data = base64.b64encode(heic_data).decode("ascii")
	file_length = len(base64_data)

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

	current_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
	debug_print(f"Starting transmission of image: {compressed_file_name} with {num_buffers} buffers.")

	if bm is None:
		raise RuntimeError("BristlemouthSerial unavailable (UART busy or not present).")

	start_msg = (f"<START IMG> filename: {compressed_file_name}, "
				 f"timestamp: {current_timestamp}, length: {num_buffers}\n")
	bm.spotter_tx(start_msg.encode('ascii'))
	time.sleep(5)

	for i in range(num_buffers):
		buffer_path = os.path.join(buffer_directory, f"split_{i}.txt")
		with open(buffer_path, 'r') as buffer_file:
			buffer_data = buffer_file.read()
		buffer_to_send = f"<I{i}>{buffer_data}\n"
		bm.spotter_tx(buffer_to_send.encode('ascii'))
		debug_print(f"Sent buffer {i+1} of {num_buffers}")
		time.sleep(5)

	end_msg = "<END IMG>\n"
	bm.spotter_tx(end_msg.encode('ascii'))
	debug_print(f"Finished transmission of image: {compressed_file_name}")

def compress_and_send_image(image_path, compression_quality=25):
	"""Compress the image to HEIC, save it, and send buffers."""
	compressed_file_name, num_buffers, file_size_compressed = split_image_heic(
		image_path, compression_quality=compression_quality
	)
	send_buffers(BUFFER_DIRECTORY, compressed_file_name)
	return compressed_file_name, num_buffers, file_size_compressed

def log_message(rtc_time, compressed_image_filename, file_size_raw, file_size_compressed,
				compression_quality, num_buffers, execution_time, within_window, cpu_temp):
	file_exists = os.path.isfile(LOG_FILE)
	with open(LOG_FILE, 'a', newline='') as file:
		writer = csv.writer(file)
		if not file_exists:
			writer.writerow([
				"RTC Timestamp (UTC)", "Compressed Image Filename", "Raw File Size (bytes)",
				"Compressed File Size (bytes)", "Compression Quality", "Number of Buffers",
				"Execution Time (minutes)", "Within Time Window", "CPU Temp (°C)"
			])
		writer.writerow([
			rtc_time.strftime('%Y-%m-%dT%H:%M:%SZ'), compressed_image_filename, file_size_raw,
			file_size_compressed, COMPRESSION_QUALITY, num_buffers,
			f"{execution_time:.2f}", within_window, f"{cpu_temp:.2f}"
		])
		debug_print(f"Raw image size: {file_size_raw} bytes")
		debug_print(f"Quality: {COMPRESSION_QUALITY}")
		debug_print(f"Compressed image size: {file_size_compressed} bytes")
		debug_print(f"Buffers: {num_buffers}")
		debug_print(f"Execution Time: {execution_time:.2f} min")
		debug_print(f"Within Window: {within_window}")
		debug_print(f"CPU Temp: {cpu_temp:.2f}°C")
		debug_print(" ")

def close_bm_serial():
	"""Close the BM serial once complete"""
	if bm is not None:
		try:
			bm.uart.close()
		except Exception:
			pass
	return 0

