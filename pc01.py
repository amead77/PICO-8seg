#!/usr/bin/env python3
import time
import subprocess
import serial
import sys

def get_cpu_usage():
    try:
        # Use psutil if available
        import psutil
        return int(psutil.cpu_percent(interval=0.1))
    except ImportError:
        # Fallback to simple method
        try:
            result = subprocess.run(['top', '-bn1'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            for line in lines:
                if line.startswith('Cpu(s):'):
                    # Parse the first value (user CPU)
                    cpu_line = line.split(',')[0]
                    user_cpu = cpu_line.split(':')[1].strip()
                    return int(float(user_cpu.split('%')[0]))
        except:
            return 0

def main():
    # Find serial port
    ports = ['/dev/ttyACM0', '/dev/ttyUSB0', '/dev/ttyACM1']
    serial_port = None
    
    for port in ports:
        try:
            ser = serial.Serial(port, 115200, timeout=1)
            ser.close()
            serial_port = port
            print("Found port: {}".format(port))
            break
        except:
            continue
    
    if serial_port is None:
        print("No serial port found")
        sys.exit(1)
    
    try:
        ser = serial.Serial(serial_port, 115200, timeout=1)
        print("Connected to {}".format(serial_port))
        
        while True:
            cpu_usage = get_cpu_usage()
            # Send without newline - just the number
            ser.write("{}\r\n".format(cpu_usage).encode())
            print("Sent CPU usage: {}%".format(cpu_usage))
            time.sleep(0.25)
            
    except KeyboardInterrupt:
        print("Stopping...")
        ser.close()
    except Exception as e:
        print("Error: {}".format(e))
        ser.close()

if __name__ == "__main__":
    main()
