"""
DataBase.dll Web-based Real-time Analyzer
Flask dashboard with live variable tracking and visualization
"""

from flask import Flask, render_template, jsonify
import socket
import threading
from datetime import datetime
from collections import defaultdict
import time
import sys
import os

# Import shared DB parsing helpers from the launcher package layout.
PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_MANAGER_MAIN = os.path.join(PACKAGE_ROOT, 'db_manager_main')
if DB_MANAGER_MAIN not in sys.path:
    sys.path.insert(0, DB_MANAGER_MAIN)
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)

from db_parser import parse_dpc, parse_dpe
from path_helpers import resolve_resource_dir

app = Flask(__name__)

# Configuration
UDP_HOST = '0.0.0.0'
UDP_PORT = 9999
WEB_PORT = 5075

# Global state
variables = {}  # {path: VariableTracker}
operation_log = []
recent_changes = []
templates = {}  # {path: [template_values]} loaded from DPE files
stats = {
    'total_reads': 0,
    'total_writes': 0,
    'total_getidx': 0,
    'total_setidx': 0,
    'start_time': datetime.now()
}

class VariableTracker:
    def __init__(self, path):
        self.path = path
        self.read_count = 0
        self.write_count = 0
        self.getidx_count = 0
        self.setidx_count = 0
        self.last_value = None
        self.value_history = []
        self.last_changed = None
        self.first_seen = datetime.now()

    def record_read(self, value=None):
        self.read_count += 1
        stats['total_reads'] += 1
        if value:
            self._update_value(value)

    def record_write(self, value):
        self.write_count += 1
        stats['total_writes'] += 1
        self._update_value(value)

    def record_getidx(self, value):
        self.getidx_count += 1
        stats['total_getidx'] += 1
        if value:
            self._update_value(value)

    def record_setidx(self, value):
        self.setidx_count += 1
        stats['total_setidx'] += 1
        self._update_value(value)

    def _update_value(self, value):
        value_str = str(value)
        if self.last_value != value_str:
            old_value = self.last_value
            self.last_value = value_str
            self.last_changed = datetime.now()
            self.value_history.append((datetime.now(), value_str))

            # Track recent change
            recent_changes.insert(0, {
                'time': datetime.now().strftime('%H:%M:%S'),
                'path': self.path,
                'old': old_value,
                'new': value_str
            })

            # Keep only last 50 changes
            if len(recent_changes) > 50:
                recent_changes.pop()

            # Limit history
            if len(self.value_history) > 100:
                self.value_history = self.value_history[-100:]

    def to_dict(self, include_history=False):
        # Normalize path to lowercase for case-insensitive template lookup
        normalized_path = self.path.lower()

        data = {
            'path': self.path,
            'reads': self.read_count,
            'writes': self.write_count,
            'getidx': self.getidx_count,
            'setidx': self.setidx_count,
            'last_value': self.last_value,
            'changes': len(self.value_history),
            'last_changed': self.last_changed.strftime('%H:%M:%S') if self.last_changed else None,
            'templates': templates.get(normalized_path, [])
        }
        if include_history:
            data['history'] = [
                {'time': ts.strftime('%H:%M:%S'), 'value': val}
                for ts, val in self.value_history
            ]
        return data

def parse_log_message(message):
    """Parse UDP message"""
    try:
        if '[' not in message or '] ' not in message:
            return None

        ts_end = message.find(']')
        timestamp = message[1:ts_end]
        rest = message[ts_end+2:]

        parts = rest.split(' ', 1)
        if len(parts) < 1:
            return None

        operation = parts[0]

        if operation in ['GET', 'SET', 'GETIDX', 'SETIDX']:
            if len(parts) < 2:
                return {'op': operation, 'timestamp': timestamp}

            path = parts[1].split(' ')[0].split('=')[0]

            value = None
            index = None

            # Parse index value for SETIDX/GETIDX operations
            if operation in ['SETIDX', 'GETIDX']:
                if '->' in message:
                    # GETIDX return value: "-> 2"
                    value_start = message.find("->") + 2
                    value_part = message[value_start:].strip()
                    try:
                        index = int(value_part)
                    except ValueError:
                        pass
                elif '=' in rest:
                    # SETIDX assignment: "= 2"
                    eq_pos = rest.find('=')
                    value_part = rest[eq_pos+1:].strip()
                    try:
                        index = int(value_part)
                    except ValueError:
                        pass
            else:
                # Parse string value for GET/SET operations
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
                'path': path,
                'value': value,
                'index': index,
                'timestamp': timestamp
            }
    except:
        pass
    return None

def track_operation(parsed):
    """Update tracking with parsed operation"""
    if not parsed or 'path' not in parsed:
        return

    path = parsed['path']

    if path not in variables:
        variables[path] = VariableTracker(path)
        # Debug: Print first few variables to see path format
        if len(variables) <= 3:
            normalized = path.lower()
            print(f"DEBUG: Variable path from UDP: '{path}'")
            print(f"       Normalized: '{normalized}'")
            if normalized in templates:
                print(f"  ✓ Found template: {templates[normalized][:3]}...")
            else:
                print(f"  ✗ No template match")

    tracker = variables[path]

    # Convert index to template value for GETIDX/SETIDX operations
    display_value = None
    if parsed.get('index') is not None:
        index = parsed['index']
        normalized_path = path.lower()
        template_list = templates.get(normalized_path, [])

        if template_list and 0 <= index < len(template_list):
            template_value = template_list[index]
            display_value = f"[idx {index}] \"{template_value}\""
        else:
            # No template or out of range - just show the index
            display_value = f"[idx {index}]"

    if parsed['op'] == 'GET':
        tracker.record_read(parsed.get('value'))
    elif parsed['op'] == 'SET':
        tracker.record_write(parsed.get('value'))
    elif parsed['op'] == 'GETIDX':
        tracker.record_getidx(display_value)
    elif parsed['op'] == 'SETIDX':
        tracker.record_setidx(display_value)

    operation_log.append({
        'time': datetime.now(),
        'parsed': parsed
    })

    # Keep log manageable
    if len(operation_log) > 1000:
        operation_log.pop(0)

def load_templates():
    """Load template values from all DPC/DPE file pairs"""
    global templates

    resource_dir = str(resolve_resource_dir())

    # List of DPC/DPE file pairs to load
    dpc_files = [
        'SeamanPC', 'User', 'Relation', 'Schedule',
        'PersonalCalendar', 'LargeSchedule'
    ]

    print("Loading templates from DPC/DPE files...")

    for base_name in dpc_files:
        dpc_path = os.path.join(resource_dir, f"{base_name}.dpc")
        dpe_path = os.path.join(resource_dir, f"{base_name}.dpe")

        if not os.path.exists(dpc_path) or not os.path.exists(dpe_path):
            print(f"  Skipping {base_name} (files not found)")
            continue

        try:
            dpc_records = parse_dpc(dpc_path)
            dpe_records = parse_dpe(dpe_path, dpc_records)

            for rec in dpe_records:
                if rec['templates']:
                    # Prepend category name and normalize to lowercase for case-insensitive lookup
                    full_path = f"{base_name}\\{rec['path']}"
                    normalized_path = full_path.lower()
                    templates[normalized_path] = rec['templates']

            print(f"  Loaded {len([r for r in dpe_records if r['templates']])} templates from {base_name}")
        except Exception as e:
            print(f"  Error loading {base_name}: {e}")

    print(f"Total templates loaded: {len(templates)}")

    # Debug: Show first few template paths
    if templates:
        print("\nDEBUG: First 5 template paths:")
        for i, path in enumerate(list(templates.keys())[:5]):
            print(f"  [{i+1}] '{path}' → {len(templates[path])} options")


def udp_listener():
    """Background thread for UDP reception"""
    print(f"Starting UDP listener on {UDP_HOST}:{UDP_PORT}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_HOST, UDP_PORT))
    sock.settimeout(1.0)

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            message = data.decode('utf-8', errors='replace').strip()
            parsed = parse_log_message(message)
            if parsed:
                track_operation(parsed)
        except socket.timeout:
            continue
        except Exception as e:
            print(f"Error in UDP listener: {e}")

# Flask routes
@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/stats')
def api_stats():
    """Overall statistics"""
    uptime = (datetime.now() - stats['start_time']).total_seconds()

    return jsonify({
        'total_operations': stats['total_reads'] + stats['total_writes'] + stats['total_getidx'] + stats['total_setidx'],
        'total_reads': stats['total_reads'],
        'total_writes': stats['total_writes'],
        'total_getidx': stats['total_getidx'],
        'total_setidx': stats['total_setidx'],
        'unique_variables': len(variables),
        'uptime_seconds': int(uptime),
        'uptime_formatted': f"{int(uptime//3600)}h {int((uptime%3600)//60)}m {int(uptime%60)}s"
    })

@app.route('/api/variables')
def api_variables():
    """All variables with details"""
    return jsonify([v.to_dict() for v in variables.values()])

@app.route('/api/top_read')
def api_top_read():
    """Top 10 most read variables"""
    sorted_vars = sorted(variables.values(), key=lambda v: v.read_count, reverse=True)
    return jsonify([{'path': v.path, 'count': v.read_count} for v in sorted_vars[:10]])

@app.route('/api/top_write')
def api_top_write():
    """Top 10 most written variables"""
    sorted_vars = sorted(variables.values(), key=lambda v: v.write_count, reverse=True)
    return jsonify([{'path': v.path, 'count': v.write_count} for v in sorted_vars[:10]])

@app.route('/api/top_changed')
def api_top_changed():
    """Top 10 most changed variables"""
    sorted_vars = sorted(variables.values(), key=lambda v: len(v.value_history), reverse=True)
    return jsonify([{'path': v.path, 'count': len(v.value_history)} for v in sorted_vars[:10]])

@app.route('/api/recent_changes')
def api_recent_changes():
    """Recent value changes"""
    return jsonify(recent_changes[:20])

@app.route('/api/written_vars')
def api_written_vars():
    """Variables that have been written to"""
    written = [v.to_dict() for v in variables.values() if v.write_count > 0]
    return jsonify(sorted(written, key=lambda v: v['writes'], reverse=True))

@app.route('/api/variable/<path:varpath>')
def api_variable_detail(varpath):
    """Get detailed info for a specific variable including history"""
    if varpath in variables:
        return jsonify(variables[varpath].to_dict(include_history=True))
    return jsonify({'error': 'Variable not found'}), 404

@app.route('/api/full_history')
def api_full_history():
    """Export complete operation log with all details"""
    export_data = {
        'exported_at': datetime.now().isoformat(),
        'total_operations': len(operation_log),
        'stats': {
            'total_reads': stats['total_reads'],
            'total_writes': stats['total_writes'],
            'total_getidx': stats['total_getidx'],
            'total_setidx': stats['total_setidx'],
            'unique_variables': len(variables),
            'start_time': stats['start_time'].isoformat()
        },
        'operations': [
            {
                'time': op['time'].isoformat(),
                'operation': op['parsed']['op'],
                'path': op['parsed'].get('path', ''),
                'value': op['parsed'].get('value', ''),
                'timestamp': op['parsed'].get('timestamp', '')
            }
            for op in operation_log
        ],
        'variables': {
            path: {
                'reads': v.read_count,
                'writes': v.write_count,
                'getidx': v.getidx_count,
                'setidx': v.setidx_count,
                'last_value': v.last_value,
                'history': [
                    {'time': ts.isoformat(), 'value': val}
                    for ts, val in v.value_history
                ],
                'templates': templates.get(path.lower(), [])
            }
            for path, v in variables.items()
        }
    }
    return jsonify(export_data)

if __name__ == '__main__':
    print("=" * 60)
    print("DataBase.dll Web-based Real-time Analyzer")
    print("=" * 60)

    # Load templates from DPC/DPE files
    load_templates()

    # Start UDP listener in background
    udp_thread = threading.Thread(target=udp_listener, daemon=True)
    udp_thread.start()

    print(f"UDP Listener: {UDP_HOST}:{UDP_PORT}")
    print(f"Web Dashboard: http://localhost:{WEB_PORT}")
    print("=" * 60)
    print()

    # Start Flask server
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False, threaded=True)
