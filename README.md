# Bristlemouth Raspberry Pi Camera Project
Welcome to the Bristlemouth Project repository. This repo contains multiple components for the underwater Raspberry Pi camera system and its associated hardware. The primary focus is on the camera software running on the Raspberry Pi, while additional components such as mechanical designs, PCBA files, and remote server code are under active development.

## Repository Structure
```
Bristlemouth-Project/
├── README.md              # Overview and project information
├── LICENSE                # Apache 2.0 license details
├── camera_software/       # Software for the underwater camera (active)
├── remote_server/         # (In development) Code for parsing messages, stitching images, and integrations
├── mechanical_design/     # (In development) CAD files and mechanical drawings for the camera housing
└── pcba_design/           # (In development) PCB design files, BOMs, and Gerber files for fabrication
```

## Camera Software
The camera_software folder contains the code that runs on the Raspberry Pi inside the underwater camera system. This software is responsible for:

- Capturing images using the camera.
- Processing images (compression, splitting, and sending).
- Logging operational data (including file sizes, CPU temperature, and execution time).
- Handling hardware communications via UART.

## Installation
To install and deploy the camera software on your Raspberry Pi:

[details coming soon]


## Future Development
The following components are currently in development and will be added in future updates:

### Remote Server:
This module will parse messages from the camera, stitch images together, and integrate with external services (e.g., automatically saving images to Google Drive or posting to Slack).

### Mechanical Design:
CAD files, STEP files, and mechanical drawings for the camera housing will be provided here.

### PCBA Design:
This section will include PCB design files, BOMs, and Gerber files for those looking to fabricate their own camera PCBs.

We welcome contributions and suggestions as these components evolve.

## License
This project is licensed under the Apache License 2.0. The license is fully permissive and helps protect the Bristlemouth brand. A full copy of the license is included in the LICENSE file.


## Contributing
Contributions are welcome! If you’d like to contribute, please fork the repository, create a new branch for your feature or bug fix, and submit a pull request. For major changes, please open an issue to discuss your ideas first.

## Acknowledgments

This project was inspired by and incorporates elements from the [REMORA_RPi](https://github.com/mjpeauroi/REMORA_RPi/tree/master) project by the REMORA_RPi team. You all showed that it was possible to get this working with a RPi and BM dev kit- thanks!