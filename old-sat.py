from machine import Pin, SPI, UART
import time

# UART configuration for reading from Pi
uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))

# Pin definitions - verify these match your hardware
MOSI = 11
SCK = 10    
RCLK = 9

# Digit address codes
KILOBIT   = 0xFE
HUNDREDS  = 0xFD
TENS      = 0xFB
UNITS     = 0xF7
Dot       = 0x80

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
    0x7C, # b
    0x39, # C
    0x5E, # d
    0x79, # E
    0x71  # F
] 

# Safe Access with Bounds Checking
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
        
        # Write each digit to corresponding position
        # Note: We're using the correct mapping for 4-digit display
        self.write_cmd(KILOBIT, self.SEG8[digit0])  # Thousands
        self.write_cmd(TENS, self.SEG8[digit1])     # Hundreds  
        self.write_cmd(HUNDREDS, self.SEG8[digit2]) # Tens
        self.write_cmd(UNITS, self.SEG8[digit3])    # Units
        
        self.current_display = num_str
        
    def clear_display(self):
        '''Clear the display'''
        self.write_cmd(KILOBIT, 0x00)
        self.write_cmd(TENS, 0x00)
        self.write_cmd(HUNDREDS, 0x00)
        self.write_cmd(UNITS, 0x00)
        self.current_display = None

def main():
    # Initialize display
    display = LED_8SEG()
    
    # Clear display initially
    display.clear_display()
    
    print("CPU Display Ready - Waiting for data...")
    
    try:
        while True:
            # Check if data is available to read
            if uart.any():
                try:
                    # Read line from UART (USB connection)
                    line = uart.readline().decode('utf-8').strip()
                    if line:
                        # Convert to integer and display
                        cpu_usage = int(line)
                        print("Received CPU usage: {}%".format(cpu_usage))
                        
                        # Display the CPU usage
                        # For CPU usage (0-100%), we'll show it as 0000-0100
                        # If > 9999, cap it at 9999
                        if cpu_usage > 9999:
                            cpu_usage = 9999
                        elif cpu_usage < 0:
                            cpu_usage = 0
                        
                        display.write_all(cpu_usage)
                        
                except ValueError:
                    # If we can't parse the input, continue waiting
                    pass
                except Exception as e:
                    print("Error:", e)
                    pass
            
            time.sleep(0.1)  # Small delay to prevent excessive CPU usage
            
    except KeyboardInterrupt:
        print("Stopping display...")
        display.clear_display()

if __name__ == "__main__":
    main()
