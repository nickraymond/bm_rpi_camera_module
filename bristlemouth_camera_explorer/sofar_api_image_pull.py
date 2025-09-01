# # filename: sofar_api_image_pull.py
# # description: parse the data from API and save images + CSV file with summary of lat, lon, filename, and message
# #
# # Copyright 2025 Nick Raymond
# #
# # Licensed under the Apache License, Version 2.0 (the "License");
# # you may not use this file except in compliance with the License.
# # You may obtain a copy of the License at
# #
# #     http://www.apache.org/licenses/LICENSE-2.0
# #
# # Unless required by applicable law or agreed to in writing, software
# # distributed under the License is distributed on an "AS IS" BASIS,
# # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# # See the License for the specific language governing permissions and
# # limitations under the License.
# import argparse
# import os
# import re
# import base64
# import requests
# import csv
# from collections import defaultdict
#
#
# # Directory where parsed images and text files will be saved
# img_directory = 'parsed_images'
# csv_filename = 'spotter_data.csv'
# image_log_filename = 'spotter_image_log.csv'  # New CSV file for image logs
# TXT_TAG = "<T>"
#
# # Ensure the directories exist
# if not os.path.exists(img_directory):
#     os.makedirs(img_directory)
#
# csv_path = os.path.join(img_directory, csv_filename)
# image_log_path = os.path.join(img_directory, image_log_filename)
#
# # Ensure the CSV files exist and write headers if they don't
# if not os.path.exists(csv_path):
#     with open(csv_path, mode='w', newline='') as file:
#         writer = csv.writer(file)
#         writer.writerow(["Timestamp", "Latitude", "Longitude", "Node ID", "Decoded Value"])  # CSV header for text data
#
# if not os.path.exists(image_log_path):
#     with open(image_log_path, mode='w', newline='') as file:
#         writer = csv.writer(file)
#         writer.writerow(["Timestamp", "Latitude", "Longitude", "Node ID", "Filename", "File Size (bytes)"])  # CSV header for image logs
#
# def json_to_csv(csv_path, json_data):
#     # Check if 'data' is in json_data and if it's a list
#     if 'data' in json_data and isinstance(json_data['data'], list):
#
#         # Open the file for writing
#         with open(csv_path, mode='w', newline='') as file:
#             # Assuming all entries have the same keys, so take the keys from the first entry for the header
#             headers = json_data['data'][0].keys()
#             writer = csv.DictWriter(file, fieldnames=headers)
#             writer.writeheader()  # Write the header
#
#             # Iterate over each entry in the data array and write it to the CSV file
#             for entry in json_data['data']:
#                 writer.writerow(entry)
#     else:
#         print("Error: The provided JSON data is missing 'data' key or it's not a list.")
#
# def api_login(spotterId, token, start_date=None, end_date=None):
#     """Fetch data from the Spotter API within a specified date range."""
#     if start_date and end_date:
#         api_url_with_dates = f"https://api.sofarocean.com/api/sensor-data?spotterId={spotterId}&startDate={start_date}&endDate={end_date}&token={token}"
#     else:
#         raise ValueError("Start date and end date must be provided")
#
#     print(f"API URL for Spotter {spotterId}: {api_url_with_dates}")
#
#     response = requests.get(api_url_with_dates)
#
#     if response.status_code == 200:
#         print(f"Successfully fetched data for Spotter {spotterId}.")
#         return response.json()
#     else:
#         print(f"Failed to fetch data for Spotter {spotterId}. Status code: {response.status_code}")
#         raise Exception("API request failed.")
#
#
# def decode_hex_to_ascii(hex_string):
#     """Decode a hex string to ASCII format, handling any Unicode errors gracefully."""
#     byte_value = bytes.fromhex(hex_string)
#     try:
#         return byte_value.decode('utf-8')
#     except UnicodeDecodeError as e:
#         print(f"Error decoding byte: {byte_value[e.start:e.end]} at position {e.start}")
#         return byte_value.decode('utf-8', errors='replace')
#
#
# def save_image(decoded_value, collecting_image_data, image_data, img_directory, image_filename, saved_images_count,
#                timestamp, latitude, longitude, node_id, image_log_path, num_buffers_expected, buffers_received):
#     """Handles collecting image data, skipping filename, timestamp, and length, and saves the image once done."""
#
#     # When a new image starts
#     if '<START IMG>' in decoded_value:
#         # If a new <START IMG> is found and we're collecting data, process the current image
#         if collecting_image_data:
#             print(f"New <START IMG> found before previous image completed. Processing current image with {len(buffers_received)} chunks.")
#             save_image_if_complete(img_directory, timestamp, image_filename, image_data, saved_images_count, latitude, longitude,
#                                    node_id, image_log_path, num_buffers_expected, buffers_received)
#
#         print(f'\nStart image found from node {node_id}.')
#         collecting_image_data = True
#         image_data.clear()
#         buffers_received.clear()  # Reset for the new image
#         num_buffers_expected[0] = 0  # Reset the expected buffer count
#
#         # Extract image filename, timestamp, and length (number of expected buffers)
#         image_info = re.search(r'filename: ([^,]+), timestamp: ([^,]+), length: (\d+)', decoded_value)
#         if image_info:
#             image_filename[0] = image_info.group(1)
#             image_timestamp = image_info.group(2)
#             num_buffers_expected[0] = int(image_info.group(3))
#
#             # Ensure the filename is sanitized and retains its original extension
#             sanitized_file_name = re.sub(r'[^\w\-_\(\)\.]', '_', image_filename[0])
#             if not any(sanitized_file_name.lower().endswith(ext) for ext in [".jpg", ".heic", ".png"]):
#                 sanitized_file_name += ".jpg"  # Default to .jpg if no valid extension is found
#             image_filename[0] = sanitized_file_name
#
#             print(f"Parsed Filename: {image_filename[0]}, Timestamp: {image_timestamp}, Buffers: {num_buffers_expected[0]}")
#         else:
#             print("Warning: Could not parse the message to extract image information.")
#
#     # When receiving image chunks
#     elif collecting_image_data:
#         match = re.search(r'<I(\d+)>', decoded_value)
#         if match:
#             tag_number = int(match.group(1))
#             content = decoded_value[decoded_value.find('>') + 1:]
#             image_data.append((tag_number, content))  # Append as a tuple
#             buffers_received.add(tag_number)  # Track the buffer received using set's add method
#
#         # Check if all expected buffers have been received
#         if len(buffers_received) == num_buffers_expected[0]:
#             print(f"All expected chunks received. Processing image.")
#             save_image_if_complete(img_directory, timestamp, image_filename, image_data, saved_images_count, latitude, longitude,
#                                    node_id, image_log_path, num_buffers_expected, buffers_received)
#             collecting_image_data = False  # Reset after saving the image
#
#     return collecting_image_data
#
# def save_image_if_complete(img_directory, timestamp, image_filename, image_data, saved_images_count, latitude, longitude,
#                            node_id, image_log_path, num_buffers_expected, buffers_received):
#     """
#     Save the image and provide warnings if buffers are missing.
#     Use JSON timestamp for file name while preserving correct file extension.
#     """
#
#     # Check for missing buffers
#     expected_buffers = set(range(num_buffers_expected[0]))  # Full set of expected buffers
#     missing_buffers = sorted(list(expected_buffers - buffers_received))  # Calculate missing buffers
#
#     if missing_buffers:
#         print(f"Warning: Missing chunks. Received {len(buffers_received)} out of {num_buffers_expected[0]}.")
#         print(f"Missing chunks: {missing_buffers}")
#         # Proceed to save the image with a warning about missing buffers
#
#     if image_data:
#         # Sort based on buffer index to reconstruct the image in the correct order
#         image_data.sort(key=lambda x: x[0])
#         cleaned_base64_data = "".join([data for _, data in image_data])
#
#         try:
#             # Decode the base64-encoded image data
#             decoded_data = base64.b64decode(cleaned_base64_data)
#
#             if not os.path.exists(img_directory):
#                 os.makedirs(img_directory)
#
#             # Generate file name based on JSON timestamp with the correct file extension
#             file_extension = os.path.splitext(image_filename[0])[1].lower()
#             formatted_timestamp = timestamp.replace(':', '-').replace('T', '_').split('.')[0]
#             sanitized_file_name = f"{formatted_timestamp}_image{file_extension}"
#             file_path = os.path.join(img_directory, sanitized_file_name)
#
#             # Save the image file
#             with open(file_path, 'wb') as file:
#                 file.write(decoded_data)
#
#             file_size = os.path.getsize(file_path)
#             print(f"Image saved successfully at {file_path}, File Size: {file_size} bytes")
#
#             # Update saved images count
#             saved_images_count[0] += 1
#
#             # Log image details
#             with open(image_log_path, mode='a', newline='') as file:
#                 writer = csv.writer(file)
#                 writer.writerow([timestamp, latitude, longitude, node_id, sanitized_file_name, file_size])
#
#         except base64.binascii.Error as b64_error:
#             print(f"Base64 decoding failed: {b64_error}")
#         except Exception as e:
#             print(f"Error saving image: {e}")
#     else:
#         print("Warning: No image data collected to save.")
#
# def log_image(image_log_path, timestamp, latitude, longitude, node_id, file_path):
#     """Logs image data into the image log CSV file."""
#     file_size = os.path.getsize(file_path)
#     with open(image_log_path, mode='a', newline='') as file:
#         writer = csv.writer(file)
#         writer.writerow([timestamp, latitude, longitude, node_id, file_path, file_size])
#
#
# def process_json(json_data, img_directory_base):
#     """Splits data by bristlemouth_node_id and saves separate CSV files in subfolders."""
#
#     # Step 1: Create a main directory for this API call
#     if not os.path.exists(img_directory_base):
#         os.makedirs(img_directory_base)
#
#     # Step 2: Group data by bristlemouth_node_id using a defaultdict
#     grouped_data = defaultdict(list)
#
#     # Step 3: Loop through each entry in the JSON data and group by node_id
#     for entry in json_data['data']:
#         node_id = entry['bristlemouth_node_id']
#         grouped_data[node_id].append(entry)
#
#     # Step 4: Create subfolders and CSV files for each node_id (only in this function)
#     for node_id, entries in grouped_data.items():
#         # Create subfolder for this node_id
#         node_directory = os.path.join(img_directory_base, f"{node_id}")
#         if not os.path.exists(node_directory):
#             os.makedirs(node_directory)
#
#         # Define the CSV file path
#         csv_filename = os.path.join(node_directory, f"{node_id}.csv")
#
#         # Check if there's any data in the first entry to get the headers
#         if len(entries) > 0:
#             headers = entries[0].keys()
#         else:
#             continue  # Skip if no entries for the node
#
#         # Write data to CSV for each bristlemouth_node_id
#         with open(csv_filename, mode='w', newline='') as csv_file:
#             writer = csv.DictWriter(csv_file, fieldnames=headers)
#
#             # Write the header
#             writer.writeheader()
#
#             # Write the data rows
#             for entry in entries:
#                 writer.writerow(entry)
#
#         print(f"Data for node {node_id} saved to {csv_filename}")
#
#     return grouped_data  # Return grouped data to be used in the next function
#
# def process_grouped_data(grouped_data, img_directory_base, csv_path, image_log_path):
#     """Processes grouped data entries (sorted by bristlemouth_node_id) to extract image and text data."""
#
#     total_images_saved = 0
#
#     for node_id, entries in grouped_data.items():
#         print(f"Processing bristlemouth_node_id: {node_id}")
#
#         # Create a single directory for each bristlemouth_node_id without the "node_" prefix
#         node_img_directory = os.path.join(img_directory_base, f"{node_id}")
#         if not os.path.exists(node_img_directory):
#             os.makedirs(node_img_directory)
#
#         collecting_image_data = False
#         image_data = []
#         image_filename = [None]
#         saved_images_count = [0]
#         buffers_received = set()
#         num_buffers_expected = [0]
#
#         node_csv_path = os.path.join(node_img_directory, f"{node_id}.csv")
#
#         # Write text data for this node
#         with open(node_csv_path, mode='w', newline='') as csv_file:
#             writer = csv.DictWriter(csv_file, fieldnames=['timestamp', 'latitude', 'longitude', 'decoded_value'])
#             writer.writeheader()
#
#             for entry in entries:
#                 decoded_value = decode_hex_to_ascii(entry['value'])
#                 latitude = entry['latitude']
#                 longitude = entry['longitude']
#                 timestamp = entry['timestamp']  # Extract the timestamp from the JSON
#
#                 writer.writerow({
#                     'timestamp': timestamp,
#                     'latitude': latitude,
#                     'longitude': longitude,
#                     'decoded_value': decoded_value
#                 })
#
#                 # Pass the timestamp to the save_image function
#                 collecting_image_data = save_image(
#                     decoded_value, collecting_image_data, image_data, node_img_directory, image_filename,
#                     saved_images_count, timestamp, latitude, longitude, node_id, image_log_path,
#                     num_buffers_expected, buffers_received
#                 )
#
#         print(f"Images saved for node {node_id}: {saved_images_count[0]}")
#         total_images_saved += saved_images_count[0]
#
#     print(f"Total images saved across all node IDs: {total_images_saved}")
#
#
# def main_hardcode():
#     # Define a list of Spotter IDs to process
#     spotter_ids = ["SPOT-31593C", "SPOT-31081C"]  # Add as many IDs as needed
#
#     # Define the start and end dates for API calls
#     start_date = "2025-06-09T00:00:00Z"
#     end_date = "2025-06-11T00:00:00Z"
#
#     for spotter_id in spotter_ids:
#         print(f"\nProcessing Spotter ID: {spotter_id}")
#
#         try:
#             # Fetch API data for the current Spotter ID
#             api_data = api_login(spotter_id, start_date=start_date, end_date=end_date)
#
#             # Create a directory for this Spotter ID
#             spotter_img_directory = os.path.join(img_directory, spotter_id)
#             if not os.path.exists(spotter_img_directory):
#                 os.makedirs(spotter_img_directory)
#
#             # Step 1: Process the JSON and get the grouped data
#             grouped_data = process_json(api_data, spotter_img_directory)
#
#             # Step 2: Use the grouped data to process the images and text data
#             process_grouped_data(grouped_data, spotter_img_directory, csv_path, image_log_path)
#
#             # Step 3: Save all JSON data from API call to CSV
#             json_to_csv(csv_path, api_data)
#
#         except Exception as e:
#             print(f"Error processing Spotter ID {spotter_id}: {e}")
#
# def main(spotter_ids, start_date, end_date, token):
#     for spotter_id in spotter_ids:
#         print(f"\nProcessing Spotter ID: {spotter_id}")
#         try:
#             api_data = api_login(spotter_id, token=token, start_date=start_date, end_date=end_date)
#
#             spotter_img_directory = os.path.join(img_directory, spotter_id)
#             os.makedirs(spotter_img_directory, exist_ok=True)
#
#             grouped_data = process_json(api_data, spotter_img_directory)
#             process_grouped_data(grouped_data, spotter_img_directory, csv_path, image_log_path)
#             json_to_csv(csv_path, api_data)
#
#         except Exception as e:
#             print(f"Error processing Spotter ID {spotter_id}: {e}")
#
# # if using hardcode method
# # if __name__ == "__main__":
# #     main()
# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="Fetch and process Spotter API image data.")
#     parser.add_argument('--spotters', nargs='+', default=["SPOT-31593C"], help='List of Spotter IDs')
#     parser.add_argument('--start', default="2025-05-18T00:00:00Z", help='Start date in ISO format')
#     parser.add_argument('--end', default="2025-05-20T00:00:00Z", help='End date in ISO format')
#     parser.add_argument('--token', default="add_your_key_here", help='You API token')
#
#     args = parser.parse_args()
#     main(args.spotters, args.start, args.end, args.token)
#


# filename: sofar_api_image_pull.py
# description: parse the data from API and save images + CSV file with summary of lat, lon, filename, and message
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

import argparse
import os
import re
import base64
import requests
import csv
from collections import defaultdict

# =========================
# Config / constants
# =========================
IMG_DIRECTORY_ROOT = 'parsed_images'
CSV_FILENAME = 'spotter_data.csv'
IMAGE_LOG_FILENAME = 'spotter_image_log.csv'
TXT_TAG = "<T>"

# Flexible metadata regexes (filename/timestamp/length can vary in order/format)
META_RES = [
    # filename, timestamp, length/buffers
    re.compile(r'filename\s*[:=]\s*"?([^",]+)"?\s*[,;]\s*timestamp\s*[:=]\s*"?([^",]+)"?\s*[,;]\s*(?:length|len|buffers?)\s*[:=]\s*(\d+)', re.IGNORECASE),
    # length/buffers, timestamp, filename
    re.compile(r'(?:length|len|buffers?)\s*[:=]\s*(\d+)\s*[,;]\s*timestamp\s*[:=]\s*"?([^",]+)"?\s*[,;]\s*filename\s*[:=]\s*"?([^",]+)"?', re.IGNORECASE),
    # filename and timestamp only (no length)
    re.compile(r'filename\s*[:=]\s*"?([^",]+)"?\s*[,;]\s*timestamp\s*[:=]\s*"?([^",]+)"?', re.IGNORECASE),
]

# =========================
# File setup
# =========================
if not os.path.exists(IMG_DIRECTORY_ROOT):
    os.makedirs(IMG_DIRECTORY_ROOT)

csv_path = os.path.join(IMG_DIRECTORY_ROOT, CSV_FILENAME)
image_log_path = os.path.join(IMG_DIRECTORY_ROOT, IMAGE_LOG_FILENAME)

if not os.path.exists(csv_path):
    with open(csv_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Timestamp", "Latitude", "Longitude", "Node ID", "Decoded Value"])

if not os.path.exists(image_log_path):
    with open(image_log_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Timestamp", "Latitude", "Longitude", "Node ID", "Filename", "File Size (bytes)"])


# =========================
# Helpers
# =========================
def json_to_csv(csv_path, json_data):
    if 'data' in json_data and isinstance(json_data['data'], list) and json_data['data']:
        with open(csv_path, mode='w', newline='') as file:
            headers = json_data['data'][0].keys()
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            for entry in json_data['data']:
                writer.writerow(entry)
    else:
        print("Error: The provided JSON data is missing 'data' key or it's not a non-empty list.")


def api_login(spotterId, token, start_date=None, end_date=None):
    """Fetch data from the Spotter API within a specified date range."""
    if start_date and end_date:
        api_url_with_dates = (
            f"https://api.sofarocean.com/api/sensor-data?"
            f"spotterId={spotterId}&startDate={start_date}&endDate={end_date}&token={token}"
        )
    else:
        raise ValueError("Start date and end date must be provided")

    print(f"API URL for Spotter {spotterId}: {api_url_with_dates}")
    response = requests.get(api_url_with_dates)

    if response.status_code == 200:
        print(f"Successfully fetched data for Spotter {spotterId}.")
        return response.json()
    else:
        print(f"Failed to fetch data for Spotter {spotterId}. Status code: {response.status_code}")
        raise Exception("API request failed.")


def decode_hex_to_ascii(hex_string):
    """Decode a hex string to ASCII format, handling any Unicode errors gracefully."""
    byte_value = bytes.fromhex(hex_string)
    try:
        return byte_value.decode('utf-8')
    except UnicodeDecodeError as e:
        print(f"Error decoding byte: {byte_value[e.start:e.end]} at position {e.start}")
        return byte_value.decode('utf-8', errors='replace')


def try_parse_metadata(text):
    """
    Try multiple regex layouts. Normalize to (filename, timestamp, length_or_None).
    """
    for rx in META_RES:
        m = rx.search(text)
        if not m:
            continue
        groups = list(m.groups())
        # 3 groups: either fname, ts, len OR len, ts, fname
        if len(groups) == 3:
            if 'filename' in rx.pattern and 'timestamp' in rx.pattern:
                # fname, ts, len
                fname, ts, ln = groups[0], groups[1], int(groups[2])
                return fname, ts, ln
            else:
                # len, ts, fname
                ln, ts, fname = int(groups[0]), groups[1], groups[2]
                return fname, ts, ln
        # 2 groups: fname, ts (no length)
        elif len(groups) == 2:
            fname, ts = groups[0], groups[1]
            return fname, ts, None
    return None, None, None


def sanitize_filename(name):
    if not name:
        return None
    s = re.sub(r'[^\w\-_\(\)\.]', '_', name)
    if not any(s.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".heic", ".png"]):
        s += ".jpg"
    return s


def log_image(image_log_path, timestamp, latitude, longitude, node_id, file_path):
    """Logs image data into the image log CSV file."""
    file_size = os.path.getsize(file_path)
    with open(image_log_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, latitude, longitude, node_id, file_path, file_size])


# =========================
# Image assembly pipeline
# =========================
def save_image(decoded_value, collecting_image_data, image_data, img_directory, image_filename, saved_images_count,
               timestamp, latitude, longitude, node_id, image_log_path, num_buffers_expected, buffers_received):
    """
    Handle START/metadata/chunks/END and trigger save when appropriate.
    Tolerates missing metadata, unknown length, and partial base64.
    """

    # Detect start of image
    if '<START IMG>' in decoded_value:
        # Flush previous image if we were mid-collection
        if collecting_image_data and image_data:
            print(f"New <START IMG> found before previous image completed. Flushing partial image with {len(image_data)} chunks.")
            save_image_if_complete(img_directory, timestamp, image_filename, image_data, saved_images_count,
                                   latitude, longitude, node_id, image_log_path, num_buffers_expected, buffers_received)

        print(f'\nStart image found from node {node_id}.')
        collecting_image_data = True
        image_data.clear()
        buffers_received.clear()
        num_buffers_expected[0] = 0  # unknown until parsed
        image_filename[0] = None

        # Try to parse metadata on same line
        fname, its, length = try_parse_metadata(decoded_value)
        if fname or its or length is not None:
            if fname:
                image_filename[0] = sanitize_filename(fname)
            if length is not None:
                num_buffers_expected[0] = int(length)
            if fname or its or length is not None:
                print(f"Parsed metadata on START: filename={image_filename[0]} length={num_buffers_expected[0]} timestamp={its}")
        else:
            print("Note: No metadata parsed on START line; will watch subsequent lines.")

        return collecting_image_data

    # If we're inside an image, harvest metadata if it arrives late or collect chunks
    if collecting_image_data:
        # Try to harvest late metadata if missing
        if (image_filename[0] is None) or (num_buffers_expected[0] == 0):
            fname, its, length = try_parse_metadata(decoded_value)
            updated_meta = False
            if fname and image_filename[0] is None:
                image_filename[0] = sanitize_filename(fname)
                updated_meta = True
            if length is not None and num_buffers_expected[0] == 0:
                num_buffers_expected[0] = int(length)
                updated_meta = True
            if updated_meta:
                print(f"Parsed late metadata: filename={image_filename[0]} length={num_buffers_expected[0]} timestamp={its}")

        # Detect explicit END tag (optional if sender supports it)
        if '<END IMG>' in decoded_value:
            print("END IMG detected; flushing image.")
            save_image_if_complete(img_directory, timestamp, image_filename, image_data, saved_images_count,
                                   latitude, longitude, node_id, image_log_path, num_buffers_expected, buffers_received)
            collecting_image_data = False
            return collecting_image_data

        # Detect chunk lines: <I#>
        m = re.search(r'<I(\d+)>', decoded_value)
        if m:
            tag_number = int(m.group(1))
            # Take everything after the first '>' and keep only base64-ish characters
            raw = decoded_value[decoded_value.find('>') + 1:]
            content = re.sub(r'[^A-Za-z0-9+/=]', '', raw)
            image_data.append((tag_number, content))
            buffers_received.add(tag_number)

            # Light logging for early and max indices
            if tag_number < 4:
                print(f"Chunk received: I{tag_number} (early chunk)")
            if tag_number == max(buffers_received):
                print(f"Highest chunk index so far: I{tag_number}")

            # If we know expected count, auto-save when complete
            if num_buffers_expected[0] > 0 and len(buffers_received) == num_buffers_expected[0]:
                print(f"All expected chunks received ({num_buffers_expected[0]}). Saving image.")
                save_image_if_complete(img_directory, timestamp, image_filename, image_data, saved_images_count,
                                       latitude, longitude, node_id, image_log_path, num_buffers_expected, buffers_received)
                collecting_image_data = False

    return collecting_image_data


def save_image_if_complete(img_directory, timestamp, image_filename, image_data, saved_images_count, latitude,
                           longitude, node_id, image_log_path, num_buffers_expected, buffers_received):
    """
    Save the image and provide warnings if buffers are missing.
    Use JSON timestamp for file name if no filename was provided. Tolerate partials.
    """

    if not image_data:
        print("Warning: No image data collected to save.")
        return

    # Determine expected vs received sets if we know expected length
    expected_buffers = None
    if num_buffers_expected[0] > 0:
        expected_buffers = set(range(num_buffers_expected[0]))
        received_numbers = {i for i, _ in image_data}
        missing_buffers = sorted(list(expected_buffers - received_numbers))
        if missing_buffers:
            print(f"Warning: Missing chunks. Received {len(received_numbers)} out of {num_buffers_expected[0]}. Missing: {missing_buffers}")

    # Sort by chunk index and concatenate
    image_data.sort(key=lambda x: x[0])
    cleaned_base64_data = "".join([data for _, data in image_data])

    # Remove any stray non-base64 characters (defensive)
    cleaned_base64_data = re.sub(r'[^A-Za-z0-9+/=]', '', cleaned_base64_data)
    # Pad to multiple of 4
    pad = (-len(cleaned_base64_data)) % 4
    if pad:
        cleaned_base64_data += "=" * pad

    # Choose an output filename
    if image_filename[0]:
        file_extension = os.path.splitext(image_filename[0])[1].lower() or ".jpg"
    else:
        file_extension = ".jpg"

    formatted_timestamp = (timestamp or "unknown_time").replace(':', '-').replace('T', '_').split('.')[0]
    sanitized_file_name = f"{formatted_timestamp}_image{file_extension}"
    file_path = os.path.join(img_directory, sanitized_file_name)

    try:
        decoded_data = base64.b64decode(cleaned_base64_data, validate=False)
        if not decoded_data:
            print("Decoded data is empty; skipping save.")
            return

        os.makedirs(img_directory, exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(decoded_data)

        file_size = os.path.getsize(file_path)
        print(f"Image saved at {file_path}, File Size: {file_size} bytes")

        saved_images_count[0] += 1
        with open(image_log_path, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([timestamp, latitude, longitude, node_id, sanitized_file_name, file_size])

    except base64.binascii.Error as b64_error:
        print(f"Base64 decoding failed (partial or corrupt data): {b64_error}")
    except Exception as e:
        print(f"Error saving image: {e}")


# =========================
# Data processing
# =========================
def process_json(json_data, img_directory_base):
    """Splits data by bristlemouth_node_id and saves separate CSV files in subfolders."""
    if not os.path.exists(img_directory_base):
        os.makedirs(img_directory_base)

    grouped_data = defaultdict(list)
    for entry in json_data.get('data', []):
        node_id = entry.get('bristlemouth_node_id')
        if node_id is None:
            # Skip entries without a node id
            continue
        grouped_data[node_id].append(entry)

    for node_id, entries in grouped_data.items():
        node_directory = os.path.join(img_directory_base, f"{node_id}")
        if not os.path.exists(node_directory):
            os.makedirs(node_directory)

        csv_filename = os.path.join(node_directory, f"{node_id}.csv")

        if len(entries) > 0:
            headers = entries[0].keys()
        else:
            continue

        with open(csv_filename, mode='w', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=headers)
            writer.writeheader()
            for entry in entries:
                writer.writerow(entry)

        print(f"Data for node {node_id} saved to {csv_filename}")

    return grouped_data


def process_grouped_data(grouped_data, img_directory_base, csv_path, image_log_path):
    """Processes grouped data entries (sorted by bristlemouth_node_id) to extract image and text data."""
    total_images_saved = 0

    for node_id, entries in grouped_data.items():
        print(f"Processing bristlemouth_node_id: {node_id}")

        node_img_directory = os.path.join(img_directory_base, f"{node_id}")
        if not os.path.exists(node_img_directory):
            os.makedirs(node_img_directory)

        collecting_image_data = False
        image_data = []
        image_filename = [None]
        saved_images_count = [0]
        buffers_received = set()
        num_buffers_expected = [0]

        node_csv_path = os.path.join(node_img_directory, f"{node_id}.csv")

        with open(node_csv_path, mode='w', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=['timestamp', 'latitude', 'longitude', 'decoded_value'])
            writer.writeheader()

            last_lat = last_lon = None
            last_ts = None

            for entry in entries:
                decoded_value = decode_hex_to_ascii(entry.get('value', ''))
                latitude = entry.get('latitude')
                longitude = entry.get('longitude')
                timestamp = entry.get('timestamp')  # ISO string

                last_lat, last_lon, last_ts = latitude, longitude, timestamp

                writer.writerow({
                    'timestamp': timestamp,
                    'latitude': latitude,
                    'longitude': longitude,
                    'decoded_value': decoded_value
                })

                collecting_image_data = save_image(
                    decoded_value, collecting_image_data, image_data, node_img_directory, image_filename,
                    saved_images_count, timestamp, latitude, longitude, node_id, image_log_path,
                    num_buffers_expected, buffers_received
                )

            # End-of-stream flush: if we were mid-image, save what we have (partial)
            if collecting_image_data and image_data:
                print("End of entries; flushing partial image.")
                save_image_if_complete(node_img_directory, last_ts, image_filename, image_data, saved_images_count,
                                       last_lat, last_lon, node_id, image_log_path, num_buffers_expected, buffers_received)
                collecting_image_data = False

        print(f"Images saved for node {node_id}: {saved_images_count[0]}")
        total_images_saved += saved_images_count[0]

    print(f"Total images saved across all node IDs: {total_images_saved}")


# =========================
# Entrypoints
# =========================
def main_hardcode():
    spotter_ids = ["SPOT-31593C", "SPOT-31081C"]
    start_date = "2025-06-09T00:00:00Z"
    end_date = "2025-06-11T00:00:00Z"
    token = "add_your_key_here"

    for spotter_id in spotter_ids:
        print(f"\nProcessing Spotter ID: {spotter_id}")

        try:
            api_data = api_login(spotter_id, token=token, start_date=start_date, end_date=end_date)

            spotter_img_directory = os.path.join(IMG_DIRECTORY_ROOT, spotter_id)
            if not os.path.exists(spotter_img_directory):
                os.makedirs(spotter_img_directory)

            grouped_data = process_json(api_data, spotter_img_directory)
            process_grouped_data(grouped_data, spotter_img_directory, csv_path, image_log_path)
            json_to_csv(csv_path, api_data)

        except Exception as e:
            print(f"Error processing Spotter ID {spotter_id}: {e}")


def main(spotter_ids, start_date, end_date, token):
    for spotter_id in spotter_ids:
        print(f"\nProcessing Spotter ID: {spotter_id}")
        try:
            api_data = api_login(spotter_id, token=token, start_date=start_date, end_date=end_date)

            spotter_img_directory = os.path.join(IMG_DIRECTORY_ROOT, spotter_id)
            os.makedirs(spotter_img_directory, exist_ok=True)

            grouped_data = process_json(api_data, spotter_img_directory)
            process_grouped_data(grouped_data, spotter_img_directory, csv_path, image_log_path)
            json_to_csv(csv_path, api_data)

        except Exception as e:
            print(f"Error processing Spotter ID {spotter_id}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and process Spotter API image data.")
    parser.add_argument('--spotters', nargs='+', default=["SPOT-31593C"], help='List of Spotter IDs')
    parser.add_argument('--start', default="2025-05-18T00:00:00Z", help='Start date in ISO format')
    parser.add_argument('--end', default="2025-05-20T00:00:00Z", help='End date in ISO format')
    parser.add_argument('--token', default="add_your_key_here", help='Your API token')

    args = parser.parse_args()
    main(args.spotters, args.start, args.end, args.token)
