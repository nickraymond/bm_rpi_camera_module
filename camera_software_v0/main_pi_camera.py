# filename: main_pi_camera.py
# description: take a picture, split it up and send
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

import time
import subprocess
from datetime import datetime, timezone

from process_image import (
	capture_image, compress_and_send_image, get_cpu_temperature, get_file_size, debug_print,
	IMAGE_DIRECTORY, BUFFER_SIZE, log_message, COMPRESSION_QUALITY, RESOLUTION_KEY, DEBUG, close_bm_serial
)

# ==== CONFIGURATION ====
USE_RTC = False  # Set to True if using a hardware RTC; False will use the Pi's system clock.

# Time window in military format (e.g., 00:00 to 23:59 means "always run")
time_start = (0, 0)
time_end = (23, 59)


def get_rtc_time():
	"""Retrieve the current time from the RTC."""
	try:
		result = subprocess.run(["sudo", "hwclock", "-r"], capture_output=True, text=True)
		rtc_time_str = result.stdout.strip()
		rtc_time = datetime.strptime(rtc_time_str.split('.')[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
		debug_print(f"RTC Time: {rtc_time}")
		return rtc_time
	except Exception as e:
		debug_print(f"Error reading RTC time: {e}")
		return None


def is_within_time_window(current_time, time_start, time_end):
	"""Check if the current time is within the specified time window."""
	start_time = datetime(current_time.year, current_time.month, current_time.day, time_start[0], time_start[1]).time()
	end_time = datetime(current_time.year, current_time.month, current_time.day, time_end[0], time_end[1]).time()
	is_within = start_time <= current_time.time() < end_time
	debug_print(f"Time is within window: {is_within}")
	return is_within


def main():
	"""Main function to orchestrate the camera workflow."""
	start_time = time.time()

	# Choose the source for current time based on the USE_RTC flag.
	current_time = get_rtc_time() if USE_RTC else datetime.now()

	if current_time:
		within_window = is_within_time_window(current_time, time_start, time_end)

		if within_window:
			# Capture the raw image
			image_path = capture_image(resolution_key=RESOLUTION_KEY)
			file_size_raw = get_file_size(image_path)
			cpu_temp = get_cpu_temperature()

			# Compress the image and get details
			compressed_file_name, num_buffers, file_size_compressed = compress_and_send_image(image_path)

			# Calculate execution time
			end_time = time.time()
			execution_time = (end_time - start_time) / 60

			# Log the details; using 'within_window' for record-keeping.
			log_message(
				current_time, compressed_file_name, file_size_raw, file_size_compressed,
				COMPRESSION_QUALITY, num_buffers, execution_time, within_window, cpu_temp
			)

			close_bm_serial()
		else:
			debug_print("Not within the time window. Skipping capture.")
	else:
		debug_print("Failed to retrieve time.")


if __name__ == "__main__":
	main()
