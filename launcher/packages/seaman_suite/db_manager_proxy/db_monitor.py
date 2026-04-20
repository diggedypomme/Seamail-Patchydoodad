"""
DataBase.dll Variable Access Monitor
Receives and displays real-time UDP logs from the DataBase.dll proxy
"""

import socket
import sys
from datetime import datetime
from collections import Counter

# Configuration
UDP_HOST = '0.0.0.0'  # Listen on all interfaces for remote connections
UDP_PORT = 9999

# Statistics
stats = {
    'total_reads': 0,
    'total_writes': 0,
    'total_getindex': 0,
    'total_setindex': 0,
    'categories': Counter(),
    'keys': Counter()
}

def parse_log_line(line):
    """Extract operation type, category, and key from log line"""
    try:
        # Format: [HH:MM:SS] OP Category\key
        if '] ' not in line:
            return None, None, None

        _, rest = line.split('] ', 1)
        parts = rest.split(' ', 1)
        if len(parts) < 2:
            return None, None, None

        op = parts[0]
        if '\\' in parts[1]:
            cat_key = parts[1].split('\\', 1)
            category = cat_key[0]
            key = cat_key[1].split(' ')[0].split('=')[0]
            return op, category, key

    except:
        pass

    return None, None, None

def update_stats(line):
    """Update statistics counters"""
    op, category, key = parse_log_line(line)

    if op == 'GET':
        stats['total_reads'] += 1
    elif op == 'SET':
        stats['total_writes'] += 1
    elif op == 'GETIDX':
        stats['total_getindex'] += 1
    elif op == 'SETIDX':
        stats['total_setindex'] += 1

    if category:
        stats['categories'][category] += 1
    if key:
        stats['keys'][key] += 1

def print_stats():
    """Print statistics summary"""
    print("\n" + "="*60)
    print("STATISTICS SUMMARY")
    print("="*60)
    print(f"Total Reads:    {stats['total_reads']}")
    print(f"Total Writes:   {stats['total_writes']}")
    print(f"Total GetIndex: {stats['total_getindex']}")
    print(f"Total SetIndex: {stats['total_setindex']}")
    print()
    print("Top Categories:")
    for cat, count in stats['categories'].most_common(5):
        print(f"  {cat:20s}: {count}")
    print()
    print("Top Keys:")
    for key, count in stats['keys'].most_common(10):
        print(f"  {key:30s}: {count}")
    print("="*60)

def main():
    print("="*60)
    print("DataBase.dll Variable Access Monitor")
    print("="*60)
    print(f"Listening on {UDP_HOST}:{UDP_PORT}")
    print("Press Ctrl+C to stop and show statistics")
    print()

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_HOST, UDP_PORT))

    try:
        while True:
            # Receive data
            data, addr = sock.recvfrom(4096)
            message = data.decode('utf-8', errors='replace').strip()

            # Print to console
            print(message)

            # Update statistics
            update_stats(message)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
        print_stats()

    finally:
        sock.close()

if __name__ == '__main__':
    main()
