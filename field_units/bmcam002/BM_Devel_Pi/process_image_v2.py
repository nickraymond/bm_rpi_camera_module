# filename: process_image_v2.py
# description: all the support methods to take picture, compress, and send over BM

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

# Setup the Bristlemouth UART Serial
bm = BristlemouthSerial()

# Define the UART buffer size for BM serial coms
BUFFER_SIZE = 300

# Debug flag to control printing of messages to the terminal
DEBUG = True

# Hard-coded image directory path
IMAGE_DIRECTORY = "/home/pi/BM_Devel_Pi/images"
BUFFER_DIRECTORY = "/home/pi/BM_Devel_Pi/buffer"
LOG_FILE = "/home/pi/BM_Devel_Pi/camera_log.csv"

# Encoder image quality. This is not "compression amount".
# Convention: lower = smaller file / more compression / lower visual quality.
#             higher = larger file / less compression / higher visual quality.
IMAGE_QUALITY = 25
COMPRESSION_QUALITY = IMAGE_QUALITY  # Backward-compatible alias for older log/code references.
RESOLUTION_KEY = "720p"


# Available resolution options for IMX708 / Raspberry Pi Camera Module 3-style captures.
RESOLUTIONS = {
	# 16:9 presets — preferred when you want roughly the same wide scene/FOV
	# while reducing pixel density, file size, and transmit time.
	"native_12mp": (4608, 2592),
	"12MP": (4608, 2592),
	"4k": (3840, 2160),
	"2.7k": (2704, 1520),
	"1296p": (2304, 1296),
	"1080p": (1920, 1080),
	"720p": (1280, 720),
	"480p": (854, 480),
	"360p": (640, 360),

	# 4:3 presets — useful if intentionally cropping to a narrower/taller view.
	# This can help avoid distorted edge regions from the lens and reduce file size.
	"4_3_full_crop": (3456, 2592),
	"4_3_8mp": (3264, 2448),
	"8MP": (3264, 2448),
	"4_3_5mp": (2592, 1944),
	"5MP": (2592, 1944),
	"4_3_3mp": (2048, 1536),
	"4_3_2mp": (1600, 1200),
	"4_3_1080": (1440, 1080),
	"XGA": (1024, 768),
	"SVGA": (800, 600),
	"VGA": (640, 480),
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


def validate_image_quality(image_quality):
	"""Validate encoder image quality. 0 = smallest/lowest quality; 100 = largest/highest quality."""
	image_quality = int(image_quality)
	if not 0 <= image_quality <= 100:
		raise ValueError("image_quality must be between 0 and 100")
	return image_quality


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
	
	debug_print(f"Image saved as '{image_path}', file size = {file_size} bytes")
	debug_print(f"Resolution key: {resolution_key}, resolution: {resolution[0]}x{resolution[1]}")

	# Stop the camera
	picam2.stop()

	return image_path


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


def split_image_jpeg(image_path, buffer_directory, image_quality):
	"""Splits the image into base64-encoded buffers after JPEG encoding."""
	image_quality = validate_image_quality(image_quality)

	if os.path.exists(buffer_directory):
		shutil.rmtree(buffer_directory)
		debug_print("Deleted buffers dir")

	os.makedirs(buffer_directory, exist_ok=True)
	debug_print("Created buffers dir")

	image = cv2.imread(image_path)
	
	if image is None:
		raise ValueError(f"Failed to load image from path: {image_path}")
	
	retval, buffer = cv2.imencode('.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), image_quality])
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


def split_image_heic(image_path, image_quality=IMAGE_QUALITY):
	"""Compress the image to HEIC and split into buffers."""
	image_quality = validate_image_quality(image_quality)

	if os.path.exists(BUFFER_DIRECTORY):
		shutil.rmtree(BUFFER_DIRECTORY)
		debug_print("Deleted buffers directory")
	
	os.makedirs(BUFFER_DIRECTORY, exist_ok=True)
	debug_print("Created buffers directory")
	
	file_name_without_ext = os.path.splitext(os.path.basename(image_path))[0]
	heic_output_path = os.path.join(IMAGE_DIRECTORY, f"{file_name_without_ext}_compressed.heic")
	
	# Open the image and save it as HEIC. Quality convention:
	# lower = smaller/more compressed/lower quality, higher = larger/less compressed/higher quality.
	with Image.open(image_path) as img:
		img.save(heic_output_path, format="HEIF", quality=image_quality)
	
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
		
		start_msg = (
			f"<START IMG> filename: {compressed_file_name}, "
			f"timestamp: {current_timestamp}, length: {num_buffers}\n"
		)
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
		
		end_msg = f"<END IMG>\n"
		bm.spotter_tx(end_msg.encode('ascii'))
		debug_print(f"Finished transmission of image: {compressed_file_name}")


def compress_and_send_image(image_path, image_quality=IMAGE_QUALITY):
	"""Compress the image to HEIC, save it, and send buffers."""
	compressed_file_name, num_buffers, file_size_compressed = split_image_heic(
		image_path, image_quality=image_quality
	)
	
	send_buffers(BUFFER_DIRECTORY, compressed_file_name)
	
	return compressed_file_name, num_buffers, file_size_compressed


def log_message(
		rtc_time, compressed_image_filename, file_size_raw, file_size_compressed,
		image_quality, num_buffers, execution_time, within_window, cpu_temp
	):
		"""
		Log details to the CSV file and print a concise log message to the terminal.
		"""
		file_exists = os.path.isfile(LOG_FILE)
	
		with open(LOG_FILE, 'a', newline='') as file:
			writer = csv.writer(file)
	
			if not file_exists:
				writer.writerow([
					"RTC Timestamp (UTC)", "Compressed Image Filename", "Raw File Size (bytes)",
					"Compressed File Size (bytes)", "Image Quality", "Number of Buffers",
					"Execution Time (minutes)", "Within Time Window", "CPU Temp (°C)"
				])
	
			writer.writerow([
				rtc_time.strftime('%Y-%m-%dT%H:%M:%SZ'), compressed_image_filename, file_size_raw,
				file_size_compressed, image_quality, num_buffers,
				f"{execution_time:.2f}", within_window, f"{cpu_temp:.2f}"
			])
			
			debug_print(f"Raw image size: {file_size_raw} bytes")
			debug_print(f"Image quality: {image_quality}")
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
