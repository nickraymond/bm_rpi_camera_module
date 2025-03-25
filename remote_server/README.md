# Remote Server for Sofar API Data & Image Stitching

This module is part of the Bristlemouth Project and is designed to run on a Raspberry Pi (or any Linux-based system). It periodically queries the Sofar API, retrieves messages and image segments, and stitches the images back together.

## Repository Structure
```
remote_server/ 
├── README.md # This documentation file 
├── sofar_api_image_pull.py # Main script to pull data from the Sofar API 
```

## Requirements

- **Python 3.10**  
- Required Python libraries (install via pip):
  - `requests`
  - `Pillow` (if used for image processing)
  - Other dependencies as needed by the code

## Setup and Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/nickraymond/bm_rpi_camera_module.git
   ```
   ```
   cd Bristlemouth-Project/remote_server
    ```
## Configuration
### API Settings:

Edit `sofar_api_image_pull.py` to set authentication tokens, Spotter IDs, and start and end dates for API pull. You can input multiple SPOT ID's and it will loop over each unit to look for image files within the given time span.

```
token = "add your token"
```

```
# Define a list of Spotter IDs to process
    spotter_ids = ["SPOT-32010C","SPOT-31380C", "SPOT-32071C"]  # Add as many IDs as needed
```
```
# Define the start and end dates for API calls
    start_date = "2025-03-22T00:00:00Z" 
    end_date = "2025-03-25T00:00:00Z"
```
## Output
All images will be saved to the output folder "parsed_images". Within this folder new folders will be created for each SPOT ID. Within each SPOT ID folder will be  list of node IDs, and within each node ID folder will be all sucesfully parsed image files.
## Contributing
Contributions are welcome! Please fork the repository, create a new branch for your changes, and submit a pull request. For major changes, open an issue first to discuss your ideas.

## License
This project is licensed under the Apache License 2.0. See the LICENSE file for details.


