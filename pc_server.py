# pc_server.py
# this is the server part that runs on a linux pc and serves cpu or ram stats to the the pico w client.
# by default it outputs cpu %, add 'ram' to the command line to output ram usage.
# updated so 'both' on the cmd line switches context every second.
#
import socket
import time
import subprocess
import threading
import sys

#AUTO-V
version = "v0.1-2025/12/07r13"





def get_cpu_usage():
    """Get current CPU usage percentage"""
    try:
        # Try using psutil if available
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

def get_ram_usage():
    """Get current RAM usage in gigabytes with 1 decimal point"""
    try:
        # Try using psutil if available
        import psutil
        used_bytes = psutil.virtual_memory().used
        used_gb = used_bytes / (1024.0 ** 3)
        return round(used_gb, 1)
    except ImportError:
        # Fallback to simple method
        try:
            result = subprocess.run(['free', '-b'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            for line in lines:
                if line.startswith('Mem:'):
                    # Parse memory usage in bytes
                    parts = line.split()
                    used_bytes = float(parts[2])
                    used_gb = used_bytes / (1024.0 ** 3)
                    return round(used_gb, 1)
        except:
            return 0.0

def handle_client(client_socket, address, mode='cpu'):
    """Handle a connected client"""
    print("Client connected from:", address)
    try:
        toggle = True  # For 'both' mode - start with CPU
        toggle_counter = 0  # local counter: 4 * 0.25s = 1s
        while True:
            # Get usage based on mode
            if mode == 'ram':
                usage = get_ram_usage()
                # RAM usage doesn't use suffix - keep decimal format
                data_to_send = "{}".format(usage)
                print("Sent RAM usage: {} GB".format(usage))
            elif mode == 'both':
                # Alternate between CPU and RAM every second
                if toggle:
                    usage = get_cpu_usage()
                    data_to_send = "{}C".format(usage)  # Suffix 'C' for CPU
                    print("Sent CPU usage: {}%".format(usage))
                else:
                    usage = get_ram_usage()
                    data_to_send = "{}".format(usage)  # RAM without suffix
                    print("Sent RAM usage: {} GB".format(usage))
                # increment local counter and flip every 4 loops (1 second)
                toggle_counter += 1
                if toggle_counter >= 4:
                    toggle = not toggle
                    toggle_counter = 0
            else:  # 'cpu' mode (default)
                usage = get_cpu_usage()
                data_to_send = "{}C".format(usage)  # Suffix 'C' for CPU
                print("Sent CPU usage: {}%".format(usage))
            
            # Send to client
            client_socket.send("{}\r\n".format(data_to_send).encode())
            
            # Wait before next update
            time.sleep(0.25)
            
    except Exception as e:
        print("Client error:", e)
    finally:
        client_socket.close()
        print("Client disconnected:", address)

def main():
    # Server configuration
    HOST = '192.168.1.201'  # Listen on all interfaces
    PORT = 9001
    
    # Parse command-line arguments
    mode = 'cpu'  # Default mode
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ['cpu', 'ram', 'both']:
            mode = arg
            print("Mode: {} usage".format(arg.upper()))
        else:
            print("Invalid mode: {}".format(arg))
            print("Usage: python pc_server.py [cpu|ram|both]")
            print("  cpu:  CPU usage percentage (suffix 'C')")
            print("  ram:  RAM usage in GB (with decimal point)")
            print("  both: Alternates between CPU and RAM every second")
            return
    else:
        print("Mode: CPU usage (default)")
        print("Usage: python pc_server.py [cpu|ram|both]")
        print("  cpu:  CPU usage percentage (suffix 'C')")
        print("  ram:  RAM usage in GB (with decimal point)")
        print("  both: Alternates between CPU and RAM every second")
    
    # Create socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        # Bind to address and port
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)  # Allow up to 5 connections
        print("Server listening on {}:{}".format(HOST, PORT))
        print("Waiting for connections...")
        
        while True:
            # Accept connection
            client_socket, address = server_socket.accept()
            
            # Handle client in a separate thread
            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, address, mode)
            )
            client_thread.daemon = True
            client_thread.start()
            
    except KeyboardInterrupt:
        print("\nServer stopping...")
    except Exception as e:
        print("Server error:", e)
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()