# helpers.py
import socket

def communicate(host, port, message):
    """Opens a TCP connection, sends a command, and returns the response."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, int(port)))
        s.sendall(message.encode('utf-8'))
        s.shutdown(socket.SHUT_WR)
        
        response = ""
        while True:
            data = s.recv(1024)
            if not data:
                break
            response += data.decode('utf-8')
        return response
    finally:
        s.close()