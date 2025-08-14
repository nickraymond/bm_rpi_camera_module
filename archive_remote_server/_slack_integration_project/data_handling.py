### This file provides functions for:
#  -   Saving Json data fields to .CSV
#  -   Processing value data into .TXT
#  -   Converting value data into .JPG

import csv
import base64
import os

# Function to decode hex to ASCII string
def decode_hex_to_ascii(hex_string):
    byte_value = bytes.fromhex(hex_string)
    return byte_value.decode('utf-8')

def json_to_csv(csv_path, json_data):
    # Check if 'data' is in json_data and if it's a list
    if 'data' in json_data and isinstance(json_data['data'], list):

        # Open the file for writing
        with open(csv_path, mode='w', newline='') as file:
            # Assuming all entries have the same keys, so take the keys from the first entry for the header
            headers = json_data['data'][0].keys()
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()  # Write the header 

            # Iterate over each entry in the data array and write it to the CSV file
            for entry in json_data['data']:
                writer.writerow(entry)
    else:
        print("Error: The provided JSON data is missing 'data' key or it's not a list.")

def save_txt_entry(txt_path, latitude, longitude, timestamp, decoded_value):
    # Ensure the function receives already-decoded values and writes them to the specified text file

    # Open the text file to append the new data
    with open(txt_path, 'a') as file:  # 'a' ensures that data is appended instead of overwritten
        # Prepare the string to write to the file
        line = f"Latitude: {latitude}, Longitude: {longitude}, Timestamp: {timestamp}, Value: {decoded_value}\n"
        
        # Write the formatted string to the file
        file.write(line)


# Image entry save function
# Assumes all img data is contained in "image_data"
# "img_index" is the number that specifies the transmitted image (if we have <START IMG 24> img_index=24)
# "output_directory" is the directory in which the img is saved to

def save_img_entry(image_data, img_index, output_directory):
    # Sort image data by tag number
    image_data.sort(key=lambda x: x[0])  # Sort by the tag number (first element of tuple)
    cleaned_base64_data = "".join([data for _, data in image_data])
    decoded_data = base64.b64decode(cleaned_base64_data)
    file_path = os.path.join(output_directory, f'image{img_index}.jpg')
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    with open(file_path, 'wb') as file:
        file.write(decoded_data)
    print(f"Image saved to {file_path}")
