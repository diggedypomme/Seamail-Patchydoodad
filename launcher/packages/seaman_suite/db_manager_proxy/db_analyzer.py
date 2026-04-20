"""
DataBase.dll Enhanced Variable Analyzer
Real-time analytics with change tracking, value history, and visualizations
"""

import socket
import sys
from datetime import datetime
from collections import Counter, defaultdict
import time

# Configuration
UDP_HOST = '0.0.0.0'
UDP_PORT = 9999

# ANSI color codes for highlighting
class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'

# Global tracking
variables = {}  # {full_path: VariableTracker}
operation_log = []  # Full chronological log
change_events = []  # Only value changes

class VariableTracker:
    def __init__(self, full_path):
        self.full_path = full_path
        self.read_count = 0
        self.write_count = 0
        self.getidx_count = 0
        self.setidx_count = 0
        self.last_value = None
        self.value_history = []  # [(timestamp, value)]
        self.last_changed = None
        self.first_seen = datetime.now()

    def record_read(self, value=None):
        self.read_count += 1
        if value is not None:
            self._update_value(value)

    def record_write(self, value):
        self.write_count += 1
        self._update_value(value)

    def record_getidx(self, value):
        self.getidx_count += 1
        self._update_value(value)

    def record_setidx(self, value):
        self.setidx_count += 1
        self._update_value(value)

    def _update_value(self, value):
        value_str = str(value)
        if self.last_value != value_str:
            self.last_changed = datetime.now()
            self.last_value = value_str
            self.value_history.append((datetime.now(), value_str))

            # Limit history to last 20 values
            if len(self.value_history) > 20:
                self.value_history = self.value_history[-20:]

    def get_change_count(self):
        return len(self.value_history)

def parse_log_message(message):
    """Parse incoming UDP message and extract details"""
    try:
        if '[' not in message or '] ' not in message:
            return None

        # Extract timestamp
        ts_end = message.find(']')
        timestamp = message[1:ts_end]
        rest = message[ts_end+2:]

        # Parse operation
        parts = rest.split(' ', 1)
        if len(parts) < 1:
            return None

        operation = parts[0]

        # Parse based on operation type
        if operation in ['GET', 'SET', 'GETIDX', 'SETIDX']:
            if len(parts) < 2:
                return {'op': operation, 'timestamp': timestamp}

            path_part = parts[1].split(' ')[0].split('=')[0]

            # Extract value if present
            value = None
            if '->' in message:
                value_start = message.find("->") + 2
                value_part = message[value_start:].strip()
                if value_part.startswith("'") and value_part.endswith("'"):
                    value = value_part[1:-1]
                else:
                    value = value_part
            elif '=' in rest:
                eq_pos = rest.find('=')
                value_part = rest[eq_pos+1:].strip()
                if "'" in value_part:
                    value = value_part.split("'")[1]

            return {
                'op': operation,
                'path': path_part,
                'value': value,
                'timestamp': timestamp,
                'raw': message
            }
    except Exception as e:
        pass

    return None

def track_operation(parsed):
    """Update global tracking with parsed operation"""
    if not parsed or 'path' not in parsed:
        return

    path = parsed['path']

    # Create tracker if new variable
    if path not in variables:
        variables[path] = VariableTracker(path)

    tracker = variables[path]

    # Record operation
    if parsed['op'] == 'GET':
        tracker.record_read(parsed.get('value'))
    elif parsed['op'] == 'SET':
        tracker.record_write(parsed.get('value'))
    elif parsed['op'] == 'GETIDX':
        tracker.record_getidx(parsed.get('value'))
    elif parsed['op'] == 'SETIDX':
        tracker.record_setidx(parsed.get('value'))

    # Log operation
    operation_log.append({
        'time': datetime.now(),
        'parsed': parsed
    })

    # Track changes
    if tracker.last_changed and (datetime.now() - tracker.last_changed).total_seconds() < 1:
        change_events.append({
            'time': datetime.now(),
            'path': path,
            'value': tracker.last_value,
            'op': parsed['op']
        })

def print_bar_chart(items, title, max_width=40):
    """Print ASCII bar chart"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{title}{Colors.RESET}")
    print("=" * 60)

    if not items:
        print("  (no data)")
        return

    max_count = max(count for _, count in items) if items else 1

    for label, count in items[:10]:
        bar_width = int((count / max_count) * max_width)
        bar = "█" * bar_width
        print(f"  {label:30s} {Colors.GREEN}{bar}{Colors.RESET} {count}")

def print_dashboard():
    """Print real-time analytics dashboard"""
    print("\033[2J\033[H")  # Clear screen and move to top

    print(f"{Colors.BOLD}{Colors.MAGENTA}╔══════════════════════════════════════════════════════════════╗{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}║     DataBase.dll Enhanced Variable Analyzer                 ║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}╚══════════════════════════════════════════════════════════════╝{Colors.RESET}")

    # Overall stats
    total_ops = len(operation_log)
    total_vars = len(variables)
    total_reads = sum(v.read_count for v in variables.values())
    total_writes = sum(v.write_count for v in variables.values())
    total_getidx = sum(v.getidx_count for v in variables.values())
    total_setidx = sum(v.setidx_count for v in variables.values())

    print(f"\n{Colors.BOLD}OVERALL STATISTICS{Colors.RESET}")
    print(f"  Total Operations:  {Colors.YELLOW}{total_ops}{Colors.RESET}")
    print(f"  Unique Variables:  {Colors.YELLOW}{total_vars}{Colors.RESET}")
    print(f"  Reads (GET):       {Colors.GREEN}{total_reads}{Colors.RESET}")
    print(f"  Writes (SET):      {Colors.RED}{total_writes}{Colors.RESET}")
    print(f"  Index Gets:        {Colors.CYAN}{total_getidx}{Colors.RESET}")
    print(f"  Index Sets:        {Colors.CYAN}{total_setidx}{Colors.RESET}")

    # Most read variables
    most_read = sorted(
        [(v.full_path, v.read_count) for v in variables.values()],
        key=lambda x: x[1],
        reverse=True
    )
    print_bar_chart(most_read, "TOP 10 MOST READ VARIABLES")

    # Most written variables
    most_written = sorted(
        [(v.full_path, v.write_count) for v in variables.values()],
        key=lambda x: x[1],
        reverse=True
    )
    print_bar_chart(most_written, "TOP 10 MOST WRITTEN VARIABLES")

    # Most changed variables
    most_changed = sorted(
        [(v.full_path, v.get_change_count()) for v in variables.values()],
        key=lambda x: x[1],
        reverse=True
    )
    if any(count > 0 for _, count in most_changed):
        print_bar_chart(most_changed, "TOP 10 MOST CHANGED VARIABLES")

    # Recent changes
    if change_events:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}RECENT VALUE CHANGES (Last 10){Colors.RESET}")
        print("=" * 60)
        for event in change_events[-10:]:
            time_str = event['time'].strftime('%H:%M:%S')
            print(f"  {Colors.CYAN}[{time_str}]{Colors.RESET} {Colors.YELLOW}{event['op']}{Colors.RESET} {event['path']}")
            print(f"    → {Colors.GREEN}{event['value']}{Colors.RESET}")

    print(f"\n{Colors.BOLD}Press Ctrl+C for detailed report{Colors.RESET}\n")

def print_detailed_report():
    """Print comprehensive final report"""
    print("\n" + "=" * 80)
    print(f"{Colors.BOLD}{Colors.MAGENTA}DETAILED VARIABLE ANALYSIS REPORT{Colors.RESET}")
    print("=" * 80)

    # All variables with full details
    print(f"\n{Colors.BOLD}ALL TRACKED VARIABLES ({len(variables)} total){Colors.RESET}")
    print("-" * 80)

    for path in sorted(variables.keys()):
        v = variables[path]
        print(f"\n{Colors.CYAN}{path}{Colors.RESET}")
        print(f"  Reads: {v.read_count}  Writes: {v.write_count}  GetIdx: {v.getidx_count}  SetIdx: {v.setidx_count}")
        print(f"  Current Value: {Colors.GREEN}{v.last_value}{Colors.RESET}")
        print(f"  Value Changes: {v.get_change_count()}")

        if v.value_history:
            print(f"  {Colors.BOLD}Value History:{Colors.RESET}")
            for ts, val in v.value_history[-5:]:  # Last 5 values
                print(f"    [{ts.strftime('%H:%M:%S')}] {val}")

    # Write statistics
    written_vars = [v for v in variables.values() if v.write_count > 0]
    print(f"\n{Colors.BOLD}{Colors.RED}WRITTEN VARIABLES ({len(written_vars)} total){Colors.RESET}")
    print("-" * 80)
    for v in sorted(written_vars, key=lambda x: x.write_count, reverse=True):
        print(f"  {v.full_path:50s} {Colors.RED}{v.write_count:4d} writes{Colors.RESET}  Last: {v.last_value}")

    # Save to file
    output_file = f"database_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("DATABASE VARIABLE ANALYSIS REPORT\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write("=" * 80 + "\n\n")

        for path in sorted(variables.keys()):
            v = variables[path]
            f.write(f"{path}\n")
            f.write(f"  R:{v.read_count} W:{v.write_count} GetIdx:{v.getidx_count} SetIdx:{v.setidx_count}\n")
            f.write(f"  Last Value: {v.last_value}\n")
            f.write(f"  Changes: {v.get_change_count()}\n")
            if v.value_history:
                f.write(f"  History:\n")
                for ts, val in v.value_history:
                    f.write(f"    [{ts.strftime('%H:%M:%S')}] {val}\n")
            f.write("\n")

    print(f"\n{Colors.GREEN}Report saved to: {output_file}{Colors.RESET}")

def main():
    print("=" * 60)
    print("DataBase.dll Enhanced Variable Analyzer")
    print("=" * 60)
    print(f"Listening on {UDP_HOST}:{UDP_PORT}")
    print("Dashboard updates every 2 seconds")
    print("Press Ctrl+C for detailed report")
    print()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.1)  # Non-blocking with timeout
    sock.bind((UDP_HOST, UDP_PORT))

    last_update = time.time()

    try:
        while True:
            try:
                # Receive data (non-blocking)
                data, addr = sock.recvfrom(4096)
                message = data.decode('utf-8', errors='replace').strip()

                # Parse and track
                parsed = parse_log_message(message)
                if parsed:
                    track_operation(parsed)
            except socket.timeout:
                pass

            # Update dashboard every 2 seconds
            if time.time() - last_update > 2.0:
                print_dashboard()
                last_update = time.time()

    except KeyboardInterrupt:
        print("\n\nAnalysis stopped by user.")
        print_detailed_report()

    finally:
        sock.close()

if __name__ == '__main__':
    main()
