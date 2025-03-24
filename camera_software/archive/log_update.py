# filename: log_update.py
# description: create a log file to count number of photos taken, then increment counter and update log file with new value

import os

def check_and_create_log_file(log_file_path):
	"""
	Check if the log file exists, if not create it and initialize with the number 1.
	"""
	if not os.path.exists(log_file_path):
		# Create the log file and initialize the first entry with 1
		with open(log_file_path, 'w') as log_file:
			log_file.write("1\n")
		return 1  # Return 1 as the initial value
	return None  # Indicate that the file already exists

def read_last_entry(log_file_path):
	"""
	Read the log file and get the last entry which is the largest number in the list.
	"""
	with open(log_file_path, 'r') as log_file:
		entries = log_file.readlines()
		if entries:
			# Read the last non-empty line and convert it to an integer
			last_entry = int(entries[-1].strip())
			return last_entry
		else:
			raise ValueError("Log file is empty, which should not happen.")

def append_new_entry(log_file_path, new_value):
	"""
	Append the new value to the log file.
	"""
	with open(log_file_path, 'a') as log_file:
		log_file.write(f"{new_value}\n")

def main():
	log_file_path = "log.txt"  # Log file name, created in the working directory

	# Step 1: Check if the log file exists, if not create it and initialize it with 1
	initial_value = check_and_create_log_file(log_file_path)
	
	# If the log file was just created, output the initial value and exit
	if initial_value is not None:
		print(initial_value)
		return

	# Step 2: If the log file exists, read the last entry
	last_entry = read_last_entry(log_file_path)

	# Step 3: Increment the last entry value by 1
	new_value = last_entry + 1

	# Step 4: Append the new value to the log file
	append_new_entry(log_file_path, new_value)

	# Step 5: Output the new value for use by another program
	print(new_value)

if __name__ == "__main__":
	main()
