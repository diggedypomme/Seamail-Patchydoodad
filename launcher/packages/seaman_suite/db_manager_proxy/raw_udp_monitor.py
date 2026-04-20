"""
Raw UDP Log Monitor
Shows ALL messages from DataBase.dll proxy without parsing
"""

import socket
from datetime import datetime

UDP_HOST = '0.0.0.0'
UDP_PORT = 9999

print("=" * 70)
print("RAW UDP MESSAGE MONITOR")
print("=" * 70)
print(f"Listening on {UDP_HOST}:{UDP_PORT}")
print("Showing ALL messages (no parsing)")
print("Press Ctrl+C to stop")
print("=" * 70)
print()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_HOST, UDP_PORT))

try:
    while True:
        data, addr = sock.recvfrom(4096)
        message = data.decode('utf-8', errors='replace').strip()
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"[{timestamp}] {message}")
except KeyboardInterrupt:
    print("\n\nStopped.")
finally:
    sock.close()
