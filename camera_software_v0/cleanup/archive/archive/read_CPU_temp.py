# filename: read_CPU_temp.py

import subprocess

def get_cpu_temp():
	"""
	Read the Raspberry Pi's CPU core temperature.
	
	Returns:
		float: The CPU temperature in degrees Celsius.
	"""
	# Use the command 'vcgencmd measure_temp' to get the CPU temperature
	result = subprocess.run(['vcgencmd', 'measure_temp'], capture_output=True, text=True)
	
	# Extract the temperature value from the output (format is like: temp=48.8'C)
	temp_str = result.stdout.strip()
	temp_value = float(temp_str.split('=')[1].replace("'C", ""))
	
	return temp_value

if __name__ == "__main__":
	# Call the function and print the CPU temperature
	cpu_temp = get_cpu_temp()
	print(cpu_temp)
