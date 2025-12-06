# source for raspberry pi pico w to display cpu usage on waveshare 8-segment display
# this code cannot display all 4 digits at the same time. it needs to continuously update the display to maintain the output.
#
#
#
#!/usr/bin/env python3
import time
from machine import Pin, SPI, UART
import sys

# Pin definitions for Waveshare 8-segment display
# Adjust these based on your actual connections
SPI_MOSI = 11
SPI_SCK = 10
SPI_CS = 9

# Pin definitions - verify these match your hardware
MOSI = 11
SCK = 10
RCLK = 9

# Digit address codes for 4-digit 8-segment display
DIGIT_ADDR = [
    0xFE,  # Digit 1 (leftmost)
    0xFD,  # Digit 2
    0xFB,  # Digit 3
    0xF7   # Digit 4 (rightmost)
]

# Segment codes for 0-9, A-F (common cathode)
SEGMENT_CODES = [
    0x3F,  # 0
    0x06,  # 1
    0x5B,  # 2
    0x4F,  # 3
    0x66,  # 4
    0x6D,  # 5
    0x7D,  # 6
    0x07,  # 7
    0x7F,  # 8
    0x6F,  # 9
    0x77,  # A
    0x7C,  # b
    0x39,  # C
    0x5E,  # d
    0x79,  # E
    0x71   # F
]

# Define SEG8Code for LED_8SEG class
SEG8Code = [
    0x3F,  # 0
    0x06,  # 1
    0x5B,  # 2
    0x4F,  # 3
    0x66,  # 4
    0x6D,  # 5
    0x7D,  # 6
    0x07,  # 7
    0x7F,  # 8
    0x6F   # 9
]

def get_digit_value(num, digit_pos):
    """Get the digit value for a specific position"""
    if digit_pos == 0:
        return num // 1000
    elif digit_pos == 1:
        return (num // 100) % 10
    elif digit_pos == 2:
        return (num // 10) % 10
    else:  # digit_pos == 3
        return num % 10

class WaveshareDisplay:
    def __init__(self, mosi_pin, sck_pin, cs_pin):
        # Initialize SPI
        self.spi = machine.SPI(1, baudrate=1000000, polarity=0, phase=0)
        self.cs = machine.Pin(cs_pin, machine.Pin.OUT)
        self.cs.value(1)  # CS high (inactive)
        self.mosi = machine.Pin(mosi_pin)
        self.sck = machine.Pin(sck_pin)

    def write_digit(self, digit_pos, value):
        """Write a value to a specific digit"""
        if digit_pos < 0 or digit_pos > 3:
            return

        # Convert value to segment code
        if value < 0 or value > 15:
            segment_code = 0x00  # Blank
        else:
            segment_code = SEGMENT_CODES[value]

        # Send command
        self.cs.value(0)  # CS low (active)

        # Send address
        self.spi.write(bytes([DIGIT_ADDR[digit_pos]]))

        # Send data
        self.spi.write(bytes([segment_code]))

        self.cs.value(1)  # CS high (inactive)

    def display_number(self, number):
        """Display a 4-digit number"""
        # Handle negative numbers
        if number < 0:
            number = 0
        elif number > 9999:
            number = 9999

        # Display each digit
        for i in range(4):
            digit_value = get_digit_value(number, i)
            self.write_digit(i, digit_value)

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
        time.sleep(0.002)

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

    def update_display(self):
        '''Update display to maintain current state'''
        if self.current_display is not None:
            self.write_all(self.current_display)

    def clear_display(self):
        '''Clear all digits'''
        self.write_cmd(KILOBIT, 0x00)
        self.write_cmd(HUNDREDS, 0x00)
        self.write_cmd(TENS, 0x00)
        self.write_cmd(UNITS, 0x00)
        self.current_display = None

def main():
    print("Starting main program...")

    # Initialize display
    display = LED_8SEG()

    # Clear display first
    display.clear_display()
    time.sleep(0.5)

    # Continuous update demonstration
    print("Continuous update test...")
    display.write_all("9999")

    # Keep display updated for 10 seconds
    start_time = time.time()
    while time.time() - start_time < 10:
        display.update_display()  # This ensures display stays active
        #time.sleep(0.002)  # Small delay to prevent excessive updates

    # Clear display
    display.clear_display()
    print("Test complete!")

# Run the main function
if __name__ == "__main__":
    main()
