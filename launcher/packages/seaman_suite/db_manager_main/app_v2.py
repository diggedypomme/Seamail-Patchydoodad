"""
app_v2.py — Database Editor V2: Cleaner table view with change tracking

Improvements over V1:
  - Full table view instead of tree navigation (easier to scan)
  - Refresh button + auto-refresh with configurable interval
  - Change tracking: highlights modified values + change log panel
  - Inline editing

Usage:
  cd db_editor
  venv\\Scripts\\python app_v2.py
  → http://localhost:5074
"""

import os
import shutil
import json
import sys
from datetime import datetime
from flask import Flask, render_template, jsonify, request, session

from db_parser import parse_udb, parse_dpc, save_udb

PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)

from path_helpers import resolve_seamail_root

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SEAMAIL = str(resolve_seamail_root())


def get_file_lists(seamail_path):
    """Get UDB and DPC file lists for a given SeaMail folder."""
    hostdb = os.path.join(seamail_path, 'hostDB')
    resource = os.path.join(seamail_path, 'Resource')

    udb_files = [
        ('Seaman.udb', os.path.join(hostdb, 'Seaman.udb'), 'SeamanPC'),
        ('User.udb', os.path.join(hostdb, 'User.udb'), 'User'),
        ('Calender.udb', os.path.join(hostdb, 'Calender.udb'), 'PersonalCalendar'),
    ]

    dpc_files = [
        ('SeamanPC.dpc', os.path.join(resource, 'SeamanPC.dpc')),
        ('User.dpc', os.path.join(resource, 'User.dpc')),
        ('Relation.dpc', os.path.join(resource, 'Relation.dpc')),
        ('Schedule.dpc', os.path.join(resource, 'Schedule.dpc')),
        ('PersonalCalendar.dpc', os.path.join(resource, 'PersonalCalendar.dpc')),
        ('LargeSchedule.dpc', os.path.join(resource, 'LargeSchedule.dpc')),
    ]

    return udb_files, dpc_files


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template(
        'index_v2.html',
        initial_seamail_folder=session.get('seamail_folder', DEFAULT_SEAMAIL),
    )


@app.route('/api/set-folder', methods=['POST'])
def set_folder():
    """Set the SeaMail folder path."""
    data = request.get_json()
    folder = data.get('folder')

    if not folder or not os.path.exists(folder):
        return jsonify({'error': 'Folder does not exist'}), 400

    # Validate it has hostDB or Resource subdirs
    hostdb = os.path.join(folder, 'hostDB')
    resource = os.path.join(folder, 'Resource')

    if not os.path.exists(hostdb) and not os.path.exists(resource):
        return jsonify({'error': 'Not a valid SeaMail folder (missing hostDB and Resource)'}), 400

    session['seamail_folder'] = folder
    return jsonify({'ok': True, 'folder': folder})


@app.route('/api/files')
def list_files():
    """List all available database files."""
    seamail_path = session.get('seamail_folder', DEFAULT_SEAMAIL)
    udb_files, dpc_files = get_file_lists(seamail_path)

    udb = []
    for name, path, category in udb_files:
        if os.path.exists(path):
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
            udb.append({
                'name': name,
                'path': path,
                'category': category,
                'size': size,
                'mtime': mtime,
            })

    dpc = []
    for name, path in dpc_files:
        if os.path.exists(path):
            size = os.path.getsize(path)
            dpc.append({'name': name, 'path': path, 'size': size})

    return jsonify({'udb': udb, 'dpc': dpc, 'seamail_folder': seamail_path})


@app.route('/api/udb/<name>')
def get_udb(name):
    """Parse and return a UDB file as flat list."""
    seamail_path = session.get('seamail_folder', DEFAULT_SEAMAIL)
    udb_files, _ = get_file_lists(seamail_path)

    # Special case: "ALL" loads all UDB files
    if name == 'ALL':
        all_rows = []
        total_records = 0
        latest_mtime = 0
        errors = []

        for fname, path, category in udb_files:
            if not os.path.exists(path):
                continue

            try:
                records = parse_udb(path)
                mtime = os.path.getmtime(path)
                latest_mtime = max(latest_mtime, mtime)
                total_records += len(records)
            except PermissionError:
                error_msg = 'File locked (in use by game?)'
                errors.append(f'{fname}: {error_msg}')
                _track_error(fname, error_msg)
                continue
            except Exception as e:
                error_msg = str(e)
                errors.append(f'{fname}: {error_msg}')
                _track_error(fname, error_msg)
                continue

            for rec in records:
                if rec['elements']:
                    elem = rec['elements'][0]
                    all_rows.append({
                        'file': fname,
                        'path': rec['path'],
                        'value': elem['value'],
                        'timestamp': elem['timestamp'],
                        'history': rec['elements'][1:] if len(rec['elements']) > 1 else [],
                    })
                else:
                    all_rows.append({
                        'file': fname,
                        'path': rec['path'],
                        'value': None,
                        'timestamp': None,
                        'history': [],
                    })

        return jsonify({
            'name': 'All UDB Files',
            'category': 'Combined',
            'record_count': total_records,
            'mtime': latest_mtime,
            'records': all_rows,
            'is_combined': True,
            'errors': errors if errors else None,
        })

    # Single file
    for fname, path, category in udb_files:
        if fname == name and os.path.exists(path):
            try:
                records = parse_udb(path)
                mtime = os.path.getmtime(path)
            except PermissionError:
                error_msg = 'File locked (in use by another process)'
                _track_error(fname, error_msg)
                return jsonify({'error': f'{fname}: {error_msg}'}), 423
            except Exception as e:
                error_msg = f'Parse error: {str(e)}'
                _track_error(fname, error_msg)
                return jsonify({'error': f'{fname}: {error_msg}'}), 500

            # Convert to simple flat format
            rows = []
            for rec in records:
                if rec['elements']:
                    elem = rec['elements'][0]
                    rows.append({
                        'file': fname,
                        'path': rec['path'],
                        'value': elem['value'],
                        'timestamp': elem['timestamp'],
                        'history': rec['elements'][1:] if len(rec['elements']) > 1 else [],
                    })
                else:
                    rows.append({
                        'file': fname,
                        'path': rec['path'],
                        'value': None,
                        'timestamp': None,
                        'history': [],
                    })

            return jsonify({
                'name': fname,
                'category': category,
                'record_count': len(records),
                'mtime': mtime,
                'records': rows,
                'is_combined': False,
            })
    return jsonify({'error': f'File not found: {name}'}), 404


@app.route('/api/dpc/<name>')
def get_dpc(name):
    """Parse and return a DPC file."""
    seamail_path = session.get('seamail_folder', DEFAULT_SEAMAIL)
    _, dpc_files = get_file_lists(seamail_path)

    for fname, path in dpc_files:
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
    seamail_path = session.get('seamail_folder', DEFAULT_SEAMAIL)
    udb_files, _ = get_file_lists(seamail_path)

    for fname, path, category in udb_files:
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
        old_value = None
        now = datetime.now().strftime('%Y%m%d%H%M%S')
        for rec in records:
            if rec['path'] == target_path:
                if rec['elements']:
                    old_value = rec['elements'][0]['value']
                    rec['elements'][0]['value'] = new_value
                    rec['elements'][0]['timestamp'] = now
                else:
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

        # Track change
        _track_change(fname, target_path, old_value, new_value, now)

        return jsonify({
            'ok': True,
            'path': target_path,
            'old_value': old_value,
            'new_value': new_value,
            'timestamp': now,
        })

    return jsonify({'error': f'File not found: {name}'}), 404


@app.route('/api/changes/<name>')
def get_changes(name):
    """Get change log for a specific file."""
    change_key = f'changes_{name}'
    changes = session.get(change_key, [])
    return jsonify({'changes': changes})


@app.route('/api/changes/<name>/clear', methods=['POST'])
def clear_changes(name):
    """Clear change log for a specific file."""
    change_key = f'changes_{name}'
    session[change_key] = []
    return jsonify({'ok': True})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _track_change(filename, path, old_value, new_value, timestamp):
    """Track a change in the session."""
    change_key = f'changes_{filename}'
    changes = session.get(change_key, [])

    changes.append({
        'type': 'edit',
        'timestamp': timestamp,
        'path': path,
        'old_value': old_value,
        'new_value': new_value,
    })

    # Keep last 100 changes
    if len(changes) > 100:
        changes = changes[-100:]

    session[change_key] = changes


def _track_error(filename, error_message):
    """Track a load error in the session."""
    change_key = f'changes_{filename}'
    changes = session.get(change_key, [])

    now = datetime.now().strftime('%Y%m%d%H%M%S')
    changes.append({
        'type': 'error',
        'timestamp': now,
        'error': error_message,
    })

    # Keep last 100 changes
    if len(changes) > 100:
        changes = changes[-100:]

    session[change_key] = changes


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5074, debug=True)
