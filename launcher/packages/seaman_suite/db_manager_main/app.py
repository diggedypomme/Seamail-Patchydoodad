"""
app.py — Flask web app for viewing/editing Seaman PC database files.

Supports:
  - .udb files (IDEA-encrypted User DataBase): Seaman.udb, User.udb, Calender.udb
  - .dpc files (Database Pre-Compiled Categories): variable path templates

Usage:
  cd db_editor
  venv\\Scripts\\python app.py
  → http://localhost:5073
"""

import os
import shutil
import sys
from datetime import datetime
from flask import Flask, render_template, jsonify, request

from db_parser import parse_udb, parse_dpc, build_tree, save_udb

PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)

from path_helpers import resolve_hostdb_dir, resolve_resource_dir

app = Flask(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE = os.path.dirname(os.path.abspath(__file__))
HOSTDB = str(resolve_hostdb_dir())
RESOURCE = str(resolve_resource_dir())

# Database files: (display_name, filepath, category)
UDB_FILES = [
    ('Seaman.udb', os.path.join(HOSTDB, 'Seaman.udb'), 'SeamanPC'),
    ('User.udb', os.path.join(HOSTDB, 'User.udb'), 'User'),
    ('Calender.udb', os.path.join(HOSTDB, 'Calender.udb'), 'PersonalCalendar'),
]

DPC_FILES = [
    ('SeamanPC.dpc', os.path.join(RESOURCE, 'SeamanPC.dpc')),
    ('User.dpc', os.path.join(RESOURCE, 'User.dpc')),
    ('Relation.dpc', os.path.join(RESOURCE, 'Relation.dpc')),
    ('Schedule.dpc', os.path.join(RESOURCE, 'Schedule.dpc')),
    ('PersonalCalendar.dpc', os.path.join(RESOURCE, 'PersonalCalendar.dpc')),
    ('LargeSchedule.dpc', os.path.join(RESOURCE, 'LargeSchedule.dpc')),
]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/files')
def list_files():
    """List all available database files."""
    udb = []
    for name, path, category in UDB_FILES:
        if os.path.exists(path):
            size = os.path.getsize(path)
            udb.append({'name': name, 'path': path, 'category': category, 'size': size})

    dpc = []
    for name, path in DPC_FILES:
        if os.path.exists(path):
            size = os.path.getsize(path)
            dpc.append({'name': name, 'path': path, 'size': size})

    return jsonify({'udb': udb, 'dpc': dpc})


@app.route('/api/udb/<name>')
def get_udb(name):
    """Parse and return a UDB file as a tree."""
    for fname, path, category in UDB_FILES:
        if fname == name and os.path.exists(path):
            records = parse_udb(path)
            tree = build_tree(records)
            return jsonify({
                'name': fname,
                'category': category,
                'record_count': len(records),
                'tree': _tree_to_json(tree),
                'flat': _records_to_json(records),
            })
    return jsonify({'error': f'File not found: {name}'}), 404


@app.route('/api/dpc/<name>')
def get_dpc(name):
    """Parse and return a DPC file."""
    for fname, path in DPC_FILES:
        if fname == name and os.path.exists(path):
            records = parse_dpc(path)
            return jsonify({
                'name': fname,
                'record_count': len(records),
                'records': [{'id': rid, 'path': pname} for rid, pname in records],
            })
    return jsonify({'error': f'File not found: {name}'}), 404


@app.route('/api/udb/<name>/edit', methods=['POST'])
def edit_udb(name):
    """Edit a value in a UDB file."""
    for fname, path, category in UDB_FILES:
        if fname != name:
            continue
        if not os.path.exists(path):
            return jsonify({'error': f'File not found: {name}'}), 404

        data = request.get_json()
        target_path = data.get('path')
        new_value = data.get('value')
        if target_path is None or new_value is None:
            return jsonify({'error': 'Missing path or value'}), 400

        # Parse current file
        records = parse_udb(path)

        # Find and update the record
        found = False
        now = datetime.now().strftime('%Y%m%d%H%M%S')
        for rec in records:
            if rec['path'] == target_path:
                if rec['elements']:
                    # Update first (most recent) element
                    rec['elements'][0]['value'] = new_value
                    rec['elements'][0]['timestamp'] = now
                else:
                    # Add new element
                    rec['elements'].append({'value': new_value, 'timestamp': now})
                found = True
                break

        if not found:
            return jsonify({'error': f'Path not found: {target_path}'}), 404

        # Backup original
        backup = path + '.bak'
        if not os.path.exists(backup):
            shutil.copy2(path, backup)

        # Save
        save_udb(path, records)

        return jsonify({'ok': True, 'path': target_path, 'value': new_value, 'timestamp': now})

    return jsonify({'error': f'File not found: {name}'}), 404


@app.route('/api/udb/<name>/backup', methods=['POST'])
def backup_udb(name):
    """Create a timestamped backup of a UDB file."""
    for fname, path, category in UDB_FILES:
        if fname == name and os.path.exists(path):
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"{path}.{ts}.bak"
            shutil.copy2(path, backup_path)
            return jsonify({'ok': True, 'backup': backup_path})
    return jsonify({'error': f'File not found: {name}'}), 404


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tree_to_json(node):
    """Convert tree node to JSON-serializable dict."""
    children = []
    for child_name in sorted(node['children'].keys()):
        children.append(_tree_to_json(node['children'][child_name]))
    result = {
        'name': node['name'],
        'path': node['path'],
        'value': node['value'],
        'timestamp': node['timestamp'],
        'children': children,
    }
    if 'extra_elements' in node:
        result['history'] = node['extra_elements']
    return result


def _records_to_json(records):
    """Convert flat records to JSON list."""
    result = []
    for rec in records:
        entry = {
            'path': rec['path'],
            'value': rec['elements'][0]['value'] if rec['elements'] else None,
            'timestamp': rec['elements'][0]['timestamp'] if rec['elements'] else None,
        }
        if len(rec['elements']) > 1:
            entry['history'] = rec['elements'][1:]
        result.append(entry)
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5073, debug=True)
