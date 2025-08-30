# filename: save_image.py
# description: modular script takes inputs and saves file

# To capture and save an image with a custom name and resolution:
#save_image("my_custom_image", "12MP", "/home/pi/captured_images")

#-------------------------------------------------------------------
from picamera2 import Picamera2
import time
import os

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

def validate_resolution(resolution_key):
	"""Validate the resolution key and return the corresponding resolution."""
	if resolution_key not in RESOLUTIONS:
		raise ValueError(f"Invalid resolution key. Choose from: {', '.join(RESOLUTIONS.keys())}")
	return RESOLUTIONS[resolution_key]

def capture_image(resolution_key, image_path):
	"""Capture an image with the specified resolution and save it to the given path."""
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

	# Capture the image and save it to the specified path
	picam2.capture_file(image_path)
	print(f"Image captured and saved as '{image_path}'")

	# Stop the camera
	picam2.stop()

def save_image(image_name, resolution_key="VGA", directory_path="/path/to/your/images"):
	"""Main function to capture an image with a given name and save it in the specified directory."""
	# Validate and construct the full image path
	if not os.path.exists(directory_path):
		os.makedirs(directory_path)

	image_path = os.path.join(directory_path, f"{image_name}_{resolution_key}.jpg")
	
	# Capture the image with the specified resolution
	capture_image(resolution_key, image_path)

# Example usage:
# save_image("my_image", "12MP", "/home/pi/my_images")
