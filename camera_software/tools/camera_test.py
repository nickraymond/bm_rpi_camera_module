# filename: camera_test.py
# description: take a picture, save it to the working directory, and hard code the name. Use this to test that the hardware is working correctly.

from picamera2 import Picamera2
import time

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

# Function to take a picture with the desired resolution
def take_picture(resolution_key="VGA"):
	# Check if the provided resolution key is valid
	if resolution_key not in RESOLUTIONS:
		raise ValueError(f"Invalid resolution key. Choose from: {', '.join(RESOLUTIONS.keys())}")
	
	# Get the resolution from the dictionary
	resolution = RESOLUTIONS[resolution_key]
	
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
	
	# Capture the image
	picam2.capture_file(f"image_{resolution_key}.jpg")
	
	print(f"Image captured and saved as 'image_{resolution_key}.jpg'")


	# Stop the camera
	picam2.stop()

# Example usage: Take a picture with 12MP resolution
take_picture("VGA")
