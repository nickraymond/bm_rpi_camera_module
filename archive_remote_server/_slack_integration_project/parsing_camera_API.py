
import os
import re
import base64
import requests
import csv
from data_handling import json_to_csv
from collections import defaultdict


class ParsingCameraAPI:
    def __init__(self, token):
        self.token = token

    def api_login(self, spotter_id, start_date, end_date):
        """Fetch data from the Spotter API within a specified date range."""
        if not all([start_date, end_date, spotter_id]):
            raise ValueError("Spotter ID, start date, and end date must be provided.")

        api_url = f"https://api.sofarocean.com/api/sensor-data?spotterId={spotter_id}&startDate={start_date}&endDate={end_date}&token={self.token}"
        print(f"API URL for Spotter {spotter_id}: {api_url}")

        response = requests.get(api_url)
        if response.status_code == 200:
            print(f"Successfully fetched data for Spotter {spotter_id}.")
            return response.json()
        else:
            print(f"Failed to fetch data for Spotter {spotter_id}. Status code: {response.status_code}")
            raise Exception(f"API request failed with status code {response.status_code}.")

    def decode_hex_to_ascii(self, hex_string):
        """Decode a hex string to ASCII format."""
        byte_value = bytes.fromhex(hex_string)
        try:
            return byte_value.decode('utf-8')
        except UnicodeDecodeError as e:
            print(f"Error decoding byte: {byte_value[e.start:e.end]} at position {e.start}")
            return byte_value.decode('utf-8', errors='replace')

    def save_image_if_complete(self, img_directory, timestamp, image_filename, image_data, latitude, longitude, node_id, image_log_path):
        """Save the complete image to disk."""
        if image_data:
            # Sort chunks by index
            image_data.sort(key=lambda x: x[0])
            cleaned_base64_data = "".join([data for _, data in image_data])

            try:
                decoded_data = base64.b64decode(cleaned_base64_data)

                if not os.path.exists(img_directory):
                    os.makedirs(img_directory)

                # Generate the file name using the timestamp
                file_extension = os.path.splitext(image_filename[0])[1].lower()
                formatted_timestamp = timestamp.replace(':', '-').replace('T', '_').split('.')[0]
                sanitized_file_name = f"{formatted_timestamp}_image{file_extension}"
                file_path = os.path.join(img_directory, sanitized_file_name)

                # Save the image
                with open(file_path, 'wb') as file:
                    file.write(decoded_data)

                print(f"Image saved successfully at {file_path}")

                # Log the image details
                with open(image_log_path, mode='a', newline='') as log_file:
                    writer = csv.writer(log_file)
                    writer.writerow([timestamp, latitude, longitude, node_id, sanitized_file_name, os.path.getsize(file_path)])

                return file_path
            except Exception as e:
                print(f"Error saving image: {e}")
        else:
            print("Warning: No image data collected to save.")
        return None


    def process_json(self, json_data, img_directory, image_log_path, spotter_id):
        """Processes JSON data and saves images."""
        saved_images = []
        grouped_data = defaultdict(list)

        for entry in json_data['data']:
            node_id = entry['bristlemouth_node_id']
            grouped_data[node_id].append(entry)

        for node_id, entries in grouped_data.items():
            print(f"Processing bristlemouth_node_id: {node_id}")

            node_img_directory = os.path.join(img_directory, node_id)
            if not os.path.exists(node_img_directory):
                os.makedirs(node_img_directory)

            collecting_image_data = False
            image_data = []
            image_filename = [None]

            for entry in entries:
                decoded_value = self.decode_hex_to_ascii(entry['value'])
                latitude = entry['latitude']
                longitude = entry['longitude']
                timestamp = entry['timestamp']

                if '<START IMG>' in decoded_value:
                    if collecting_image_data:
                        file_path = self.save_image_if_complete(
                            node_img_directory, timestamp, image_filename, image_data, latitude, longitude, node_id, image_log_path
                        )
                        if file_path:
                            saved_images.append({"spotter_id": spotter_id, "node_id": node_id, "file_path": file_path})

                    collecting_image_data = True
                    image_data.clear()
                    image_filename[0] = re.search(r'filename: ([^,]+)', decoded_value).group(1)

                elif collecting_image_data:
                    match = re.search(r'<I(\d+)>', decoded_value)
                    if match:
                        tag_number = int(match.group(1))
                        content = decoded_value[decoded_value.find('>') + 1:]
                        image_data.append((tag_number, content))

            # Final save for last image
            if collecting_image_data:
                file_path = self.save_image_if_complete(
                    node_img_directory, timestamp, image_filename, image_data, latitude, longitude, node_id, image_log_path
                )
                if file_path:
                    saved_images.append({"spotter_id": spotter_id, "node_id": node_id, "file_path": file_path})

        return saved_images


    def parse_camera_data(self, spotter_ids, start_date, end_date):
        """Main method to fetch data, parse images, and return metadata for multiple SPOT IDs."""
        all_saved_images = []
        for spotter_id in spotter_ids:
            print(f"\nProcessing Spotter ID: {spotter_id}")
            img_directory = os.path.join("parsed_images", spotter_id)
            image_log_path = os.path.join(img_directory, "image_log.csv")

            if not os.path.exists(img_directory):
                os.makedirs(img_directory)

            if not os.path.exists(image_log_path):
                with open(image_log_path, mode='w', newline='') as log_file:
                    writer = csv.writer(log_file)
                    writer.writerow(["Timestamp", "Latitude", "Longitude", "Node ID", "Filename", "File Size (bytes)"])

            try:
                # Fetch data for the current Spotter ID
                json_data = self.api_login(spotter_id, start_date, end_date)

                # Process JSON data and save images
                saved_images = self.process_json(json_data, img_directory, image_log_path, spotter_id)
                all_saved_images.extend(saved_images)
            except Exception as e:
                print(f"Error processing Spotter ID {spotter_id}: {e}")

        return all_saved_images
