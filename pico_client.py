# pico_client.py
# code written for Raspberry Pi Pico W with 8-segment waveshare display
# part code came from the single example from waveshare (literally the minimum working example), rest is custom.
# updating the display is done in a thread as the waveshare device requires continuous refreshing
# the pico w code connects to pc_server.py, running on a linux pc on the same network, although that could be elsewhere.
# still some flicker from the display. put the wifi ssid and password in wifi_settings.py and upload to your pico w.

import network
import socket
import time
from machine import Pin, SPI
import sys
import select
import _thread
from wifi_settings import WIFI_SSID, WIFI_PASSWORD

#AUTO-V
version = "v0.1-2025/12/06r18"


# PC server
PC_IP = "192.168.1.201"
PC_PORT = 8080

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

# Segment codes for digits 0-9
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
        '''Write complete number to all digits'''
        # Pad to 4 digits
        num_str = pad_with_zeros(str(num_str), 4)

        # Extract individual digits
        digit0 = int(safe_get_char(num_str, 0))
        digit1 = int(safe_get_char(num_str, 1))
        digit2 = int(safe_get_char(num_str, 2))
        digit3 = int(safe_get_char(num_str, 3))

        # Write all digits
        self.write_cmd(KILOBIT, self.SEG8[digit0])
        self.write_cmd(HUNDREDS, self.SEG8[digit1])
        self.write_cmd(TENS, self.SEG8[digit2])
        self.write_cmd(UNITS, self.SEG8[digit3])

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
    """Connect to WiFi network"""
    print('setup connecting to wifi')
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print('Connecting to WiFi: '+WIFI_SSID)
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        # Wait for connection
        max_wait = 10
        while max_wait > 0:
            if wlan.status() < 0 or wlan.status() >= 3:
                break
            print('Waiting for connection: '+str(max_wait))
            time.sleep(2)
            max_wait -= 1

        if wlan.status() != 3:
            print('Failed to connect to WiFi: '+str(wlan.status()))
            return None

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

def format_value_with_decimal(value):
    """Format a float value into 4 digit display with decimal point
    Formats as: XXX.X or XX.XX depending on value
    Returns tuple: (digit0, digit1, digit2, digit3, dot_position)
    dot_position: 0-3 for which digit gets the dot, or -1 for no dot
    """
    try:
        val = float(value)
        # Format with 1 decimal place, up to 3 digits before decimal
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

# Shared variable for CPU usage
cpu_usage = None

def display_updater():
    """Function to continuously update the display"""
    display = LED_8SEG()
    display.clear_display()

    while True:
        if cpu_usage is not None:
            try:
                digit0, digit1, digit2, digit3, dot_pos = format_value_with_decimal(cpu_usage)
                
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
    counter = 0  # Counter for network retries, max 3 attempts


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

    # Connect to PC server
    sock = None
    while sock is None:
        sock = connect_to_pc()
        if sock is None:
            counter += 1
            if counter >= 3:
                print("Max retries reached (init)")
                sys.exit()
            print("Failed to connect to PC server, retrying in 10 seconds...")
            time.sleep(10)

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
                            # Convert to float and update shared variable
                            cpu_usage = float(data)
                            debug_output("Received CPU usage: {}".format(cpu_usage))
                        except ValueError:
                            print("Invalid data received:", data)

                # Small delay to prevent excessive CPU usage
                time.sleep(0.2)

            except socket.timeout:
                print("Socket timeout, attempting to reconnect...")
                sock = connect_to_pc()
                if sock is None:
                    counter += 1
                    if counter >= 3:
                        print("Max retries reached (reconnect)")
                        break
                    print("Failed to reconnect to PC server")
                    time.sleep(10)
                    continue

            except Exception as e:
                print("Error receiving data:", e)
                # Reconnect to PC server
                sock = connect_to_pc()
                if sock is None:
                    counter += 1
                    if counter >= 3:
                        print("Max retries reached (reconnect)")
                        break
                    print("Failed to reconnect to PC server")
                    time.sleep(10)
                    continue

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