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
# Update: added flag to control when to transmit image over UART

import argparse
import time
import subprocess
from datetime import datetime, timezone

from process_image_v2 import (
	capture_image, compress_and_send_image, get_cpu_temperature, get_file_size, debug_print,
	IMAGE_DIRECTORY, BUFFER_SIZE, log_message, IMAGE_QUALITY, RESOLUTION_KEY, RESOLUTIONS,
	DEBUG, close_bm_serial
)
from spotter_time_sync import should_transmit_now_from_schedule, load_camera_schedule

# ==== CONFIGURATION ====
USE_RTC = False  # Set to True if using a hardware RTC; False will use the Pi's system clock.

# Reef shipment safety gate:
# Read Spotter UTC from the BM bus, convert it using camera_schedule.yaml,
# and only continue capture/transmit inside the configured local window.
USE_SPOTTER_TIME_WINDOW = True
SCHEDULE_CONFIG_PATH = "/home/pi/BM_Devel_Pi/camera_schedule.yaml"

# Legacy local time window in military format (e.g., 00:00 to 23:59 means "always run").
# Keep this permissive. The Spotter UTC schedule is the real deployment gate.
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
	"""Check if the current time is within the legacy local time window."""
	start_time = datetime(current_time.year, current_time.month, current_time.day, time_start[0], time_start[1]).time()
	end_time = datetime(current_time.year, current_time.month, current_time.day, time_end[0], time_end[1]).time()
	is_within = start_time <= current_time.time() < end_time
	debug_print(f"Time is within window: {is_within}")
	return is_within


def get_runtime_image_settings(config_path, resolution_key_override=None, image_quality_override=None):
	"""Return image settings from YAML defaults with optional CLI overrides."""
	cfg = load_camera_schedule(config_path)

	resolution_key = resolution_key_override or cfg.resolution_key or RESOLUTION_KEY
	image_quality = image_quality_override if image_quality_override is not None else cfg.image_quality
	if image_quality is None:
		image_quality = IMAGE_QUALITY

	if resolution_key not in RESOLUTIONS:
		raise ValueError(f"Invalid resolution key '{resolution_key}'. Choose from: {', '.join(RESOLUTIONS.keys())}")

	if not (0 <= int(image_quality) <= 100):
		raise ValueError("image_quality must be between 0 and 100. Lower = smaller/more compressed; higher = better/larger.")

	return resolution_key, int(image_quality), cfg


def main(
	transmit_image=False,
	resolution_key=None,
	image_quality=None,
	skip_time_window=False,
	config_path=SCHEDULE_CONFIG_PATH,
):
	"""Main function to orchestrate the camera workflow."""
	start_time = time.time()

	try:
		runtime_resolution_key, runtime_image_quality, schedule_cfg = get_runtime_image_settings(
			config_path,
			resolution_key_override=resolution_key,
			image_quality_override=image_quality,
		)
	except Exception as e:
		debug_print(f"Image/config setup failed: {e}")
		close_bm_serial()
		return

	debug_print(f"Runtime resolution_key: {runtime_resolution_key}")
	debug_print(f"Runtime image_quality: {runtime_image_quality}")

	if skip_time_window:
		debug_print("Skipping Spotter UTC transmit-window check due to CLI flag --skip-time-window.")
	elif USE_SPOTTER_TIME_WINDOW and schedule_cfg.enforce_spotter_time_window:
		try:
			allowed, schedule_info = should_transmit_now_from_schedule(config_path)
			debug_print(f"Schedule check: {schedule_info.get('reason')}")
			debug_print(f"Schedule source_time: {schedule_info.get('source_time')}")
			debug_print(f"Schedule UTC: {schedule_info.get('utc_time')}")
			debug_print(f"Schedule local: {schedule_info.get('local_time')}")
			debug_print(f"Schedule set_system_clock: {schedule_info.get('set_system_clock')}")

			if not allowed:
				debug_print("Outside configured Spotter-time transmit window. Skipping capture/transmit.")
				close_bm_serial()
				return
		except Exception as e:
			debug_print(f"Spotter-time schedule check failed closed: {e}")
			close_bm_serial()
			return
	else:
		debug_print("Spotter UTC transmit-window check disabled by config/code. Continuing.")

	# Choose the source for current time based on the USE_RTC flag.
	current_time = get_rtc_time() if USE_RTC else datetime.now()

	if current_time:
		within_window = is_within_time_window(current_time, time_start, time_end)

		if within_window:
			# Capture the raw image
			image_path = capture_image(resolution_key=runtime_resolution_key)
			file_size_raw = get_file_size(image_path)
			cpu_temp = get_cpu_temperature()

			if transmit_image:
				# Compress and transmit image
				compressed_file_name, num_buffers, file_size_compressed = compress_and_send_image(
					image_path,
					image_quality=runtime_image_quality,
				)
			else:
				compressed_file_name = "N/A"
				num_buffers = 0
				file_size_compressed = 0

			# Calculate execution time
			end_time = time.time()
			execution_time = (end_time - start_time) / 60

			# Log the details; using 'within_window' for legacy record-keeping.
			log_message(
				current_time, compressed_file_name, file_size_raw, file_size_compressed,
				runtime_image_quality, num_buffers, execution_time, within_window, cpu_temp
			)

			close_bm_serial()
		else:
			debug_print("Not within the legacy local time window. Skipping capture.")
	else:
		debug_print("Failed to retrieve time.")


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Camera capture script with optional UART transmission.")
	parser.add_argument('--transmit', action='store_true', help='Enable transmission over UART after capture')
	parser.add_argument('--resolution-key', choices=sorted(RESOLUTIONS.keys()), default=None,
					help='Override image resolution preset for this run')
	parser.add_argument('--image-quality', type=int, default=None,
					help='Override encoder image quality 0-100. Lower = smaller/more compressed; higher = better/larger')
	parser.add_argument('--skip-time-window', action='store_true',
					help='Manual override: skip the Spotter UTC transmit-window check for this run')
	parser.add_argument('--config-path', default=SCHEDULE_CONFIG_PATH,
					help='Path to camera_schedule.yaml')
	args = parser.parse_args()

	main(
		transmit_image=args.transmit,
		resolution_key=args.resolution_key,
		image_quality=args.image_quality,
		skip_time_window=args.skip_time_window,
		config_path=args.config_path,
	)
