# pico_client.py
# code written for Raspberry Pi Pico W with 8-segment waveshare display
# part code came from the single example from waveshare (literally the minimum working example), rest is custom.
# updating the display is done in a thread as the waveshare device requires continuous refreshing
# the pico w code connects to pc_server.py, running on a linux pc on the same network, although that could be elsewhere.
# still some flicker from the display. put the wifi ssid and password in wifi_settings.py and upload to your pico w.
#
# now handles context switching from the server, so 1 display can show both cpu and ram usage. with the cpu being suffixed with a C
import network
import socket
import time
from machine import Pin, SPI
import sys
import select
import _thread
from wifi_settings import WIFI_SSID, WIFI_PASSWORD

#AUTO-V
version = "v0.1-2025/12/07r12"


# PC server
PC_IP = "192.168.1.201"
PC_PORT = 9001

# Pin definitions for 8-segment display
MOSI = 11
SCK = 10
RCLK = 9

# Digit address codes
KILOBIT   = 0xFE
HUNDREDS  = 0xFD
TENS      = 0xFB
UNITS     = 0xF7
Dot       = 0x80

# Segment codes for digits 0-9 and hex A-F
SEG8Code = [
    0x3F, # 0
    0x06, # 1
    0x5B, # 2
    0x4F, # 3
    0x66, # 4
    0x6D, # 5
    0x7D, # 6
    0x07, # 7
    0x7F, # 8
    0x6F, # 9
    0x77, # A
    0x7C, # B
    0x39, # C
    0x5E, # D
    0x79, # E
    0x71, # F
]

def safe_get_char(text, index):
    if index < len(text):
        return text[index]
    else:
        return '0'  # Return '0' for missing characters

def pad_with_zeros(text, length):
    '''Pad string with leading zeros to specified length'''
    if len(text) >= length:
        return text
    else:
        return '0' * (length - len(text)) + text

class LED_8SEG:
    def __init__(self):
        self.rclk = Pin(RCLK, Pin.OUT)
        self.rclk.value(1)  # Start with latch high
        self.spi = SPI(1, baudrate=1000000, polarity=0, phase=0, sck=Pin(SCK), mosi=Pin(MOSI))
        self.SEG8 = SEG8Code
        self.current_display = None

    def write_cmd(self, digit_addr, segment_data):
        '''Write command to specific digit'''
        self.rclk.value(0)  # Latch low
        self.spi.write(bytearray([digit_addr, segment_data]))
        self.rclk.value(1)  # Latch high
        time.sleep(0.0002)

    def write_all(self, num_str):
        '''Write complete number to all digits (supports 0-9 and A-F)'''
        # Pad to 4 digits
        num_str = pad_with_zeros(str(num_str), 4)

        # Convert each character to digit value (0-9 or A-F = 10-15)
        digits = []
        for char in num_str:
            if char.isdigit():
                digits.append(int(char))
            elif char.upper() in 'ABCDEF':
                digits.append(ord(char.upper()) - ord('A') + 10)
            else:
                digits.append(0)  # Default to 0 for invalid characters

        # Write all digits
        self.write_cmd(KILOBIT, self.SEG8[digits[0]])
        self.write_cmd(HUNDREDS, self.SEG8[digits[1]])
        self.write_cmd(TENS, self.SEG8[digits[2]])
        self.write_cmd(UNITS, self.SEG8[digits[3]])

        # Store current display state
        self.current_display = num_str

    def clear_display(self):
        '''Clear the display'''
        self.write_cmd(KILOBIT, 0x00)
        self.write_cmd(TENS, 0x00)
        self.write_cmd(HUNDREDS, 0x00)
        self.write_cmd(UNITS, 0x00)
        self.current_display = None

def connect_wifi():
    """Connect to WiFi network with retry logic"""
    print('setup connecting to wifi')
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    retry_count = 0
    initial_retry_delay = 10  # First retry after 10 seconds
    subsequent_retry_delay = 30  # Subsequent retries after 30 seconds

    while True:
        if not wlan.isconnected():
            print('Attempting to connect to WiFi: ' + WIFI_SSID)
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)

            # Wait up to 10 seconds for connection
            wait_time = 10
            while wait_time > 0:
                if wlan.status() < 0 or wlan.status() >= 3:
                    break
                print('Waiting for connection: ' + str(wait_time) + 's')
                time.sleep(1)
                wait_time -= 1

            if wlan.status() != 3:
                retry_count += 1
                if retry_count == 1:
                    print('Failed to connect to WiFi. Retrying in 10 seconds...')
                    time.sleep(initial_retry_delay)
                else:
                    print('Failed to connect to WiFi. Retrying in 30 seconds...')
                    time.sleep(subsequent_retry_delay)
                continue
        else:
            break

    print('Connected to WiFi')
    print('IP address:', wlan.ifconfig()[0])
    return wlan

def connect_to_pc():
    """Connect to PC server"""
    try:
        # Create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)  # 5 second timeout

        # Connect to PC server
        print('Connecting to PC server at {}:{}'.format(PC_IP, PC_PORT))
        sock.connect((PC_IP, PC_PORT))
        print('Connected to PC server')
        return sock
    except Exception as e:
        print('Failed to connect to PC server:', e)
        return None

def test_loop(display):
    """Test loop that counts from 0000 to 0099"""
    print("Starting test loop...")
    for i in range(9999):
        display.write_all(i)
        #time.sleep(0.2)  # Display each number for 200ms
    print("Test loop completed.")

def debug_output(output):
    """Output debug information to console"""
    print("DEBUG:", output)

def format_value_with_decimal_and_suffix(value, suffix=''):
    """Format a float value into 4 digit display with decimal point and optional suffix
    Formats as: XXX.X or XX.XX depending on value, or with hex suffix like C for CPU
    Returns tuple: (digit0, digit1, digit2, digit3, dot_position)
    dot_position: 0-3 for which digit gets the dot, or -1 for no dot
    suffix: letter to replace last digit (e.g., 'C' for CPU or 'R' for RAM)
    """
    try:
        val = float(value)
        
        # Handle suffix - replace the last digit position with the suffix letter
        if suffix and suffix.upper() in '0123456789ABCDEF':
            # Format with suffix replacing units position
            if val >= 100:
                # Format as XXX with suffix as last digit
                formatted = int(val) % 1000
                digit0 = formatted // 100
                digit1 = (formatted % 100) // 10
                digit2 = formatted % 10
                # digit3 will be the suffix
                suffix_val = ord(suffix.upper()) - ord('0') if suffix.isdigit() else ord(suffix.upper()) - ord('A') + 10
                digit3 = suffix_val
                dot_pos = -1
            else:
                # Format as XX with suffix as last digit
                formatted = int(val) % 100
                digit0 = 0
                digit1 = formatted // 10
                digit2 = formatted % 10
                suffix_val = ord(suffix.upper()) - ord('0') if suffix.isdigit() else ord(suffix.upper()) - ord('A') + 10
                digit3 = suffix_val
                dot_pos = -1
            
            return (digit0, digit1, digit2, digit3, dot_pos)
        else:
            # Original behavior with decimal point
            if val >= 100:
                # Format as XXX (no decimal)
                formatted = int(val) % 1000
                digit0 = formatted // 100
                digit1 = (formatted % 100) // 10
                digit2 = formatted % 10
                digit3 = 0
                dot_pos = -1
            else:
                # Format as XX.X
                formatted = int(val * 10) % 1000
                digit0 = 0
                digit1 = formatted // 100
                digit2 = (formatted % 100) // 10
                digit3 = formatted % 10
                dot_pos = 2  # Dot on the tens position
            
            return (digit0, digit1, digit2, digit3, dot_pos)
    except:
        return (0, 0, 0, 0, -1)

# Shared variable for CPU usage and optional suffix
cpu_usage = None
display_suffix = ''

def display_updater():
    """Function to continuously update the display"""
    global display_suffix
    display = LED_8SEG()
    display.clear_display()

    while True:
        if cpu_usage is not None:
            try:
                digit0, digit1, digit2, digit3, dot_pos = format_value_with_decimal_and_suffix(cpu_usage, display_suffix)
                
                # Write each digit with optional dot
                seg0 = display.SEG8[digit0]
                seg1 = display.SEG8[digit1]
                seg2 = display.SEG8[digit2]
                seg3 = display.SEG8[digit3]
                
                # Apply dot to appropriate digit
                if dot_pos == 1:
                    seg1 |= Dot
                elif dot_pos == 2:
                    seg2 |= Dot
                elif dot_pos == 3:
                    seg3 |= Dot
                
                # Write to display
                display.write_cmd(KILOBIT, seg0)
                display.write_cmd(HUNDREDS, seg1)
                display.write_cmd(TENS, seg2)
                display.write_cmd(UNITS, seg3)
            except Exception as e:
                debug_output("Error updating display: {}".format(e))
        #time.sleep(0.1)  # Update every 100ms

def main():
    global cpu_usage
    global display_suffix

    # Initialize display (for test loop)
    display = LED_8SEG()
    display.clear_display()

    # Run test loop
    test_loop(display)
    display.clear_display()

    # Start the display updater thread
    _thread.start_new_thread(display_updater, ())

    # Connect to WiFi
    connect_wifi()

    # Connect to PC server - retry forever every 20 seconds
    sock = None
    while True:
        sock = connect_to_pc()
        if sock is not None:
            break
        print("Failed to connect to PC server, retrying in 20 seconds...")
        time.sleep(20)

    print("Connected to PC server, ready to receive CPU data...")

    try:
        while True:
            try:
                # Use select to check if there's data available
                readable, _, _ = select.select([sock], [], [], 0.1)  # Timeout of 0.1 seconds

                if sock in readable:
                    # Receive data from PC
                    data = sock.recv(1024).decode('utf-8').strip()
                    if data:
                        try:
                            # Parse data - may contain suffix like 'C' for CPU
                            value_str = data
                            suffix = ''
                            
                            # Check if last character is a letter (suffix)
                            if value_str and value_str[-1].isalpha():
                                suffix = value_str[-1].upper()
                                value_str = value_str[:-1]
                            
                            # Convert to float and update shared variables
                            cpu_usage = float(value_str)
                            display_suffix = suffix
                            debug_output("Received data: {}{}".format(cpu_usage, suffix))
                        except ValueError:
                            print("Invalid data received:", data)
                    else:
                        # Empty data means server closed the connection
                        print("Server closed connection")
                        print("Attempting to reconnect to PC server...")
                        sock = connect_to_pc()
                        while sock is None:
                            print("Failed to reconnect to PC server, retrying in 20 seconds...")
                            time.sleep(20)
                            sock = connect_to_pc()
                        print("Reconnected to PC server")

                # Small delay to prevent excessive CPU usage
                time.sleep(0.2)

            except socket.error as e:
                print("Socket error:", e)
                print("Attempting to reconnect to PC server...")
                sock = connect_to_pc()
                while sock is None:
                    print("Failed to reconnect to PC server, retrying in 20 seconds...")
                    time.sleep(20)
                    sock = connect_to_pc()
                print("Reconnected to PC server")

            except Exception as e:
                print("Error receiving data:", e)
                # Attempt to reconnect
                sock = connect_to_pc()
                while sock is None:
                    print("Failed to reconnect to PC server, retrying in 20 seconds...")
                    time.sleep(20)
                    sock = connect_to_pc()
                print("Reconnected to PC server")

    except KeyboardInterrupt:
        print("Stopping...")
        display.clear_display()
        if sock is not None:
            sock.close()
    except Exception as e:
        print("Unexpected error:", e)
        display.clear_display()
        if sock is not None:
            sock.close()

if __name__ == "__main__":
    main()