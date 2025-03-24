# Underwater Raspberry Pi Camera with Bristlemouth 

This repository contains the source code to control the underwater Raspberry Pi camera using Bristlemouth hardware. The project is designed to capture images, process them (including compression and splitting), and log the relevant data. It also includes utility scripts for testing the camera and UART (serial) communication.

## Table of Contents

- [Overview](#overview)
- [Main Script](#main-script)
- [Helper Modules](#helper-modules)
- [Example/Test Scripts](#exampletest-scripts)
- [Configuration](#configuration)
- [License](#license)
- [Contributing](#contributing)
- [Contact](#contact)

## Overview

The system is built around the `main_pi_camera.py` script, which acts as the orchestrator for the camera workflow. It integrates image capture, processing, logging, and hardware communication (e.g., via UART). The codebase is modular and includes separate helper modules for distinct tasks such as image processing, temperature reading, and log management.

## Main Script

**main_pi_camera.py**  
This is the heart of the system. It performs the following steps:

1. **Time Retrieval:**  
   - Retrieves the current time either from a hardware RTC (if `USE_RTC` is set to `True`) or from the system clock.
   - Checks if the current time is within a specified operational time window (configurable via `time_start` and `time_end`).

2. **Image Capture & Processing:**  
   - Captures an image using the connected camera.
   - Measures the raw file size.
   - Reads the CPU temperature to monitor system health.
   - Compresses the image and splits it into manageable buffers for transmission.

3. **Logging & Cleanup:**  
   - Logs all the relevant details (timestamp, file sizes, execution time, etc.) using a dedicated logging function.
   - Closes the UART serial connection to ensure that resources are properly freed.

## Helper Modules

- **process_image_v2.py:**  
  Contains the functions that handle the image capture, compression, and transmission. It also defines key constants (e.g., image resolution, directory paths, and compression quality).

- **read_CPU_temp.py:**  
  Provides functionality to read the Raspberry Pi’s CPU temperature, which is logged to monitor hardware performance.

- **save_image.py:**  
  Responsible for saving the captured image to a specified directory on the filesystem.

- **split_and_send.py:**  
  Handles the process of splitting the compressed image into smaller parts (buffers) and sending these parts over the network or serial connection.

- **log_update.py:**  
  Manages the logging of capture events, including details such as timestamps, file sizes, and other metrics.

## Example/Test Scripts

- **bm_serial_example.py & bm_serial.py:**  
  These scripts are included to test and demonstrate UART serial communication with the Bristlemouth hardware. They can be used to verify that the serial interface is functioning correctly before deploying the main camera workflow.

- **camera_test.py:**  
  A standalone script to test the camera hardware. It allows you to quickly capture an image and verify that the camera is properly connected and configured.

- **uart_test.py:**  
  Focuses on testing the UART interface. It is useful for debugging communication issues between the Raspberry Pi and other hardware components.

## Configuration

The system includes several configuration options:

- **USE_RTC:**  
  A boolean flag defined in `main_pi_camera.py` that determines whether the system should use a hardware RTC for timekeeping (`True`) or fall back to the system clock (`False`).

- **Time Window:**  
  The operational time window is configurable via `time_start` and `time_end` (in military time), controlling when the camera should capture images.

You can adjust these settings directly in the code or later extend the system to read them from environment variables or a configuration file.

## License

This project is licensed under the **Apache License 2.0**. A full copy of the license is included in the [LICENSE](LICENSE) file in the repository root. This license is fully permissive and protects the Bristlemouth brand while allowing others to use, modify, and distribute the code.

**Where to add the license details:**
- Place a `LICENSE` file in the root directory of your repository with the full text of the Apache 2.0 license.
- Include a short license header in the source files (optional but recommended for clarity).

## Contributing

Contributions are welcome! Please follow the standard fork-and-pull request workflow and include tests where applicable.

