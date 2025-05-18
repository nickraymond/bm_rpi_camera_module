# filename: NR_data_pull_v11.py >>> Remora_v11.py

# description: parse the data from API and save images + CSV file with summary of lat, lon, filename,
# TODO
# add info to the spotter_image_log: number of messages created, number of messages received, error messages
import os
import re
import base64
import requests
import csv
from data_handling import json_to_csv, save_img_entry, save_txt_entry
from collections import defaultdict



# Specify Spotter ID and API Token
# #spotterId = "SPOT-31380C" # BM camera module on SPARC
# spotterId = "SPOT-32071C" # BM camera module deck, RTC does not work
##spotterId = "SPOT-32010C" # BM camera module

#token = "90bda8b0a39b9570b548ab6f7a1aea" # sofar_eng key
token = "019058d08091ed2b1f96e774344874" # nick's admin key
#token = "add your token"


# Directory where parsed images and text files will be saved
img_directory = 'parsed_images'
csv_filename = 'spotter_data.csv'
image_log_filename = 'spotter_image_log.csv'  # New CSV file for image logs
TXT_TAG = "<T>"

# Ensure the directories exist
if not os.path.exists(img_directory):
    os.makedirs(img_directory)

csv_path = os.path.join(img_directory, csv_filename)
image_log_path = os.path.join(img_directory, image_log_filename)

# Ensure the CSV files exist and write headers if they don't
if not os.path.exists(csv_path):
    with open(csv_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Timestamp", "Latitude", "Longitude", "Node ID", "Decoded Value"])  # CSV header for text data

if not os.path.exists(image_log_path):
    with open(image_log_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Timestamp", "Latitude", "Longitude", "Node ID", "Filename", "File Size (bytes)"])  # CSV header for image logs


def api_login(spotterId, start_date=None, end_date=None):
    """Fetch data from the Spotter API within a specified date range."""
    if start_date and end_date:
        api_url_with_dates = f"https://api.sofarocean.com/api/sensor-data?spotterId={spotterId}&startDate={start_date}&endDate={end_date}&token={token}"
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


def save_image(decoded_value, collecting_image_data, image_data, img_directory, image_filename, saved_images_count,
               timestamp, latitude, longitude, node_id, image_log_path, num_buffers_expected, buffers_received):
    """Handles collecting image data, skipping filename, timestamp, and length, and saves the image once done."""

    # When a new image starts
    if '<START IMG>' in decoded_value:
        # If a new <START IMG> is found and we're collecting data, process the current image
        if collecting_image_data:
            print(f"New <START IMG> found before previous image completed. Processing current image with {len(buffers_received)} chunks.")
            save_image_if_complete(img_directory, timestamp, image_filename, image_data, saved_images_count, latitude, longitude,
                                   node_id, image_log_path, num_buffers_expected, buffers_received)

        print(f'\nStart image found from node {node_id}.')
        collecting_image_data = True
        image_data.clear()
        buffers_received.clear()  # Reset for the new image
        num_buffers_expected[0] = 0  # Reset the expected buffer count

        # Extract image filename, timestamp, and length (number of expected buffers)
        image_info = re.search(r'filename: ([^,]+), timestamp: ([^,]+), length: (\d+)', decoded_value)
        if image_info:
            image_filename[0] = image_info.group(1)
            image_timestamp = image_info.group(2)
            num_buffers_expected[0] = int(image_info.group(3))

            # Ensure the filename is sanitized and retains its original extension
            sanitized_file_name = re.sub(r'[^\w\-_\(\)\.]', '_', image_filename[0])
            if not any(sanitized_file_name.lower().endswith(ext) for ext in [".jpg", ".heic", ".png"]):
                sanitized_file_name += ".jpg"  # Default to .jpg if no valid extension is found
            image_filename[0] = sanitized_file_name

            print(f"Parsed Filename: {image_filename[0]}, Timestamp: {image_timestamp}, Buffers: {num_buffers_expected[0]}")
        else:
            print("Warning: Could not parse the message to extract image information.")

    # When receiving image chunks
    elif collecting_image_data:
        match = re.search(r'<I(\d+)>', decoded_value)
        if match:
            tag_number = int(match.group(1))
            content = decoded_value[decoded_value.find('>') + 1:]
            image_data.append((tag_number, content))  # Append as a tuple
            buffers_received.add(tag_number)  # Track the buffer received using set's add method

        # Check if all expected buffers have been received
        if len(buffers_received) == num_buffers_expected[0]:
            print(f"All expected chunks received. Processing image.")
            save_image_if_complete(img_directory, timestamp, image_filename, image_data, saved_images_count, latitude, longitude,
                                   node_id, image_log_path, num_buffers_expected, buffers_received)
            collecting_image_data = False  # Reset after saving the image

    return collecting_image_data

def save_image_if_complete(img_directory, timestamp, image_filename, image_data, saved_images_count, latitude, longitude,
                           node_id, image_log_path, num_buffers_expected, buffers_received):
    """
    Save the image and provide warnings if buffers are missing.
    Use JSON timestamp for file name while preserving correct file extension.
    """

    # Check for missing buffers
    expected_buffers = set(range(num_buffers_expected[0]))  # Full set of expected buffers
    missing_buffers = sorted(list(expected_buffers - buffers_received))  # Calculate missing buffers

    if missing_buffers:
        print(f"Warning: Missing chunks. Received {len(buffers_received)} out of {num_buffers_expected[0]}.")
        print(f"Missing chunks: {missing_buffers}")
        # Proceed to save the image with a warning about missing buffers

    if image_data:
        # Sort based on buffer index to reconstruct the image in the correct order
        image_data.sort(key=lambda x: x[0])
        cleaned_base64_data = "".join([data for _, data in image_data])

        try:
            # Decode the base64-encoded image data
            decoded_data = base64.b64decode(cleaned_base64_data)

            if not os.path.exists(img_directory):
                os.makedirs(img_directory)

            # Generate file name based on JSON timestamp with the correct file extension
            file_extension = os.path.splitext(image_filename[0])[1].lower()
            formatted_timestamp = timestamp.replace(':', '-').replace('T', '_').split('.')[0]
            sanitized_file_name = f"{formatted_timestamp}_image{file_extension}"
            file_path = os.path.join(img_directory, sanitized_file_name)

            # Save the image file
            with open(file_path, 'wb') as file:
                file.write(decoded_data)

            file_size = os.path.getsize(file_path)
            print(f"Image saved successfully at {file_path}, File Size: {file_size} bytes")

            # Update saved images count
            saved_images_count[0] += 1

            # Log image details
            with open(image_log_path, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([timestamp, latitude, longitude, node_id, sanitized_file_name, file_size])

        except base64.binascii.Error as b64_error:
            print(f"Base64 decoding failed: {b64_error}")
        except Exception as e:
            print(f"Error saving image: {e}")
    else:
        print("Warning: No image data collected to save.")

def log_image(image_log_path, timestamp, latitude, longitude, node_id, file_path):
    """Logs image data into the image log CSV file."""
    file_size = os.path.getsize(file_path)
    with open(image_log_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, latitude, longitude, node_id, file_path, file_size])


def process_json(json_data, img_directory_base):
    """Splits data by bristlemouth_node_id and saves separate CSV files in subfolders."""

    # Step 1: Create a main directory for this API call
    if not os.path.exists(img_directory_base):
        os.makedirs(img_directory_base)

    # Step 2: Group data by bristlemouth_node_id using a defaultdict
    grouped_data = defaultdict(list)

    # Step 3: Loop through each entry in the JSON data and group by node_id
    for entry in json_data['data']:
        node_id = entry['bristlemouth_node_id']
        grouped_data[node_id].append(entry)

    # Step 4: Create subfolders and CSV files for each node_id (only in this function)
    for node_id, entries in grouped_data.items():
        # Create subfolder for this node_id
        node_directory = os.path.join(img_directory_base, f"{node_id}")
        if not os.path.exists(node_directory):
            os.makedirs(node_directory)

        # Define the CSV file path
        csv_filename = os.path.join(node_directory, f"{node_id}.csv")

        # Check if there's any data in the first entry to get the headers
        if len(entries) > 0:
            headers = entries[0].keys()
        else:
            continue  # Skip if no entries for the node

        # Write data to CSV for each bristlemouth_node_id
        with open(csv_filename, mode='w', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=headers)

            # Write the header
            writer.writeheader()

            # Write the data rows
            for entry in entries:
                writer.writerow(entry)

        print(f"Data for node {node_id} saved to {csv_filename}")

    return grouped_data  # Return grouped data to be used in the next function

def process_grouped_data(grouped_data, img_directory_base, csv_path, image_log_path):
    """Processes grouped data entries (sorted by bristlemouth_node_id) to extract image and text data."""

    total_images_saved = 0

    for node_id, entries in grouped_data.items():
        print(f"Processing bristlemouth_node_id: {node_id}")

        # Create a single directory for each bristlemouth_node_id without the "node_" prefix
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

        # Write text data for this node
        with open(node_csv_path, mode='w', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=['timestamp', 'latitude', 'longitude', 'decoded_value'])
            writer.writeheader()

            for entry in entries:
                decoded_value = decode_hex_to_ascii(entry['value'])
                latitude = entry['latitude']
                longitude = entry['longitude']
                timestamp = entry['timestamp']  # Extract the timestamp from the JSON

                writer.writerow({
                    'timestamp': timestamp,
                    'latitude': latitude,
                    'longitude': longitude,
                    'decoded_value': decoded_value
                })

                # Pass the timestamp to the save_image function
                collecting_image_data = save_image(
                    decoded_value, collecting_image_data, image_data, node_img_directory, image_filename,
                    saved_images_count, timestamp, latitude, longitude, node_id, image_log_path,
                    num_buffers_expected, buffers_received
                )

        print(f"Images saved for node {node_id}: {saved_images_count[0]}")
        total_images_saved += saved_images_count[0]

    print(f"Total images saved across all node IDs: {total_images_saved}")


def main():
    # Define a list of Spotter IDs to process
    spotter_ids = ["SPOT-31593C"]  # Add as many IDs as needed

    start_date = "2025-05-17T00:00:00Z"
    end_date = "2025-05-19T00:00:00Z"

    for spotter_id in spotter_ids:
        print(f"\nProcessing Spotter ID: {spotter_id}")

        try:
            # Fetch API data for the current Spotter ID
            api_data = api_login(spotter_id, start_date=start_date, end_date=end_date)

            # Create a directory for this Spotter ID
            spotter_img_directory = os.path.join(img_directory, spotter_id)
            if not os.path.exists(spotter_img_directory):
                os.makedirs(spotter_img_directory)

            # Step 1: Process the JSON and get the grouped data
            grouped_data = process_json(api_data, spotter_img_directory)

            # Step 2: Use the grouped data to process the images and text data
            process_grouped_data(grouped_data, spotter_img_directory, csv_path, image_log_path)

            # Step 3: Save all JSON data from API call to CSV
            json_to_csv(csv_path, api_data)

        except Exception as e:
            print(f"Error processing Spotter ID {spotter_id}: {e}")


if __name__ == "__main__":
    main()
