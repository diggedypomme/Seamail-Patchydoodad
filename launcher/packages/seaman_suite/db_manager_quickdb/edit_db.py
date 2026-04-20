"""
edit_db.py — Generic UDB Variable Editor
========================================
Edits any key in a .udb file with automatic backups and logging.
Supports interactive mode and command-line automation.
"""

import sys
import os
import shutil
import datetime
import argparse

# --- Import DB parsing libs ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_ROOT = os.path.dirname(SCRIPT_DIR)

# Check multiple possible locations so the script still works after being
# moved into the launcher package structure.
possible_dirs = [
    os.path.join(PACKAGE_ROOT, 'db_manager_main'),   # Launcher package layout
    os.path.join(PACKAGE_ROOT, 'db_editor'),         # Older developer layout
    os.path.join(SCRIPT_DIR, 'db_editor'),           # Local bundled layout
]

imported = False
for d in possible_dirs:
    if os.path.exists(d):
        sys.path.insert(0, d)
        try:
            from db_parser import parse_udb, save_udb
            imported = True
            break
        except ImportError:
            sys.path.pop(0)

if not imported:
    print("\nERROR: Could not find a compatible database parser folder or 'db_parser' module.")
    print("Checked locations: {0}".format(possible_dirs))
    sys.exit(1)

if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)

from path_helpers import resolve_seamail_root

# --- Config ---
BACKUP_DIR = os.path.join(SCRIPT_DIR, 'backups')

# Common search locations
SEARCH_DIRS = [
    os.path.join(str(resolve_seamail_root()), 'hostDB'),
    str(resolve_seamail_root()),
    r'C:\sm\Vivarium\SeaMail\hostDB',
    r'C:\sm\Vivarium\SeaMail',
]

def get_timestamp():
    return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

def find_udbs():
    found = []
    for d in SEARCH_DIRS:
        if not os.path.exists(d): continue
        for f in os.listdir(d):
            if f.lower().endswith('.udb'):
                found.append(os.path.join(d, f))
    return found

def get_val(records, path):
    for r in records:
        if r['path'].lower() == path.lower() and r['elements']:
            return r['elements'][0]['value']
    return None

def set_val(records, path, value):
    ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    for r in records:
        if r['path'].lower() == path.lower():
            old_val = r['elements'][0]['value'] if r['elements'] else None
            r['elements'] = [] if value is None else [{'value': value, 'timestamp': ts}]
            return old_val
    
    # New record if not found
    records.append({'path': path, 'elements': [] if value is None else [{'value': value, 'timestamp': ts}]})
    return None

def to_full_width(text):
    """Convert standard ASCII to Full-width (Zen-kaku) with Shift-JIS compatibility."""
    chars = []
    # Use unichr on Py2, chr on Py3
    char_func = unichr if sys.version_info[0] < 3 else chr
    
    for c in text:
        code = ord(c)
        if c == '-': # Use the specific minus sign the game prefers
            chars.append(char_func(0x2212))
        elif 0x21 <= code <= 0x7E:
            chars.append(char_func(code + 0xFEE0))
        elif code == 0x20: # Space
            chars.append(char_func(0x3000))
        else:
            chars.append(c)
    return "".join(chars)

def main():
    parser = argparse.ArgumentParser(description="Generic UDB Variable Editor")
    parser.add_argument("--file", help="Path to the .udb file to edit")
    parser.add_argument("--set", action="append", help="Key=Value pair to set")
    parser.add_argument("--search", help="Search for a key pattern")
    args = parser.parse_args()

    if not args.file:
        # Interactive Mode
        print("\n=== Seaman Database Editor ===")
        udbs = find_udbs()
        if not udbs:
            print("Error: No .udb files found.")
            return
        for i, path in enumerate(udbs):
            print("  {0}: {1}".format(i+1, path))
        try:
            choice = input("\nSelect database (1-{0}): ".format(len(udbs))).strip()
            if not choice: return
            target_path = udbs[int(choice)-1]
        except:
            print("Invalid choice.")
            return
    else:
        target_path = args.file
        if not os.path.exists(target_path):
            print("Error: File not found: {0}".format(target_path))
            return

    records = parse_udb(target_path)

    if args.set:
        for s in args.set:
            if '=' not in s: continue
            key, val = s.split('=', 1)
            if val.startswith("@FW "): val = to_full_width(val[4:])
            elif val.lower() == "none" or val == "": val = None
            print("Setting {0} -> {1}".format(key, val))
            set_val(records, key, val)
        save_udb(target_path, records)
        print("Success: Database updated.")
        return

    if args.search:
        query = args.search.lower()
        for r in records:
            if query in r['path'].lower():
                print("  {0} -> {1}".format(r['path'], get_val(records, r['path'])))
        return

    # Simple interactive loop
    while True:
        print("\n[S] Search [E] Edit [Q] Quit")
        cmd = input("Choice: ").strip().upper()
        if cmd == 'Q': break
        if cmd == 'S':
            query = input("Search: ").strip().lower()
            for r in records:
                if query in r['path'].lower():
                    print("  {0} -> {1}".format(r['path'], get_val(records, r['path'])))
        if cmd == 'E':
            key = input("Key: ").strip()
            if not key: continue
            print("Current: {0}".format(get_val(records, key)))
            val = input("New value: ").strip()
            if val.startswith("@FW "): val = to_full_width(val[4:])
            elif val == "": val = None
            set_val(records, key, val)
            save_udb(target_path, records)
            print("Updated.")

if __name__ == '__main__':
    main()
