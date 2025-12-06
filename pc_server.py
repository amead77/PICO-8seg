# pc_server.py
import socket
import time
import subprocess
import threading
import sys

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

def handle_client(client_socket, address):
    """Handle a connected client"""
    print("Client connected from:", address)
    
    try:
        while True:
            # Get CPU usage
            cpu_usage = get_cpu_usage()
            
            # Send to client
            client_socket.send("{}\r\n".format(cpu_usage).encode())
            print("Sent CPU usage: {}%".format(cpu_usage))
            
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
    PORT = 8080
    
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
                args=(client_socket, address)
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