"""
db_parser.py — Parse Seaman PC database files (.dpc, .dpe, .udb)

DPC = Database Pre-Compiled: maps record_id → variable path name
DPE = Database Pre-compiled Elements: template/default values
UDB = User DataBase: IDEA-encrypted save files containing current values

UDB plaintext structure (after IDEA decryption):
  REPEAT until end:
    [uint32 name_length]        — 4 bytes (0xFFFFFFFF = end of file)
    [char[name_length] name]    — XOR 0xFF encoded path (e.g. "User\\Age")
    ELEMENTS until 0xFFFF:
      [uint16 data_length]      — 2 bytes (0xFFFF = end of this node)
      [char[data_length] value] — XOR 0xFF encoded value string
      [char[15] timestamp]      — raw ASCII timestamp "YYYYMMDDHHmmss\\0"
"""

import struct
import os
import sys
from idea_cipher import decrypt_udb, encrypt_udb

PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)

from path_helpers import resolve_seamail_root


def xor_decode(data):
    """XOR 0xFF decode: flip each byte until first 0x00."""
    result = bytearray()
    for b in data:
        if b == 0x00:
            break
        result.append(b ^ 0xFF)
    # Values may be Shift-JIS Japanese text; paths are ASCII
    try:
        return result.decode('shift_jis')
    except (UnicodeDecodeError, LookupError):
        return result.decode('ascii', errors='replace')


def xor_encode(text):
    """XOR 0xFF encode a string (add null terminator)."""
    if text is None: text = ""
    encoded = bytearray()
    
    # Try Shift-JIS first as it's the game's native format
    # We use 'replace' to ensure we don't crash on odd characters
    # but we try to keep as much Shift-JIS as possible.
    try:
        raw = text.encode('shift_jis', errors='replace')
    except (UnicodeEncodeError, LookupError):
        raw = text.encode('ascii', errors='replace')
        
    for ch in raw:
        # On Py2, ch is a str(1), on Py3 it's an int
        b = ord(ch) if isinstance(ch, str) else ch
        encoded.append(b ^ 0xFF)
    encoded.append(0x00 ^ 0xFF)  # XORed null terminator? 
    # Wait, the original game adds a null terminator (0x00) AFTER XORing? 
    # Or is the null terminator itself XORed?
    # Original logic: encoded.append(ch ^ 0xFF); encoded.append(0x00)
    # This means the 0x00 is NOT XORed.
    # Let's fix that back to original.
    
    encoded = bytearray()
    for ch in raw:
        b = ord(ch) if isinstance(ch, str) else ch
        encoded.append(b ^ 0xFF)
    encoded.append(0x00) 
    return bytes(encoded)


def parse_dpc(filepath):
    """
    Parse a .dpc file (Database Pre-Compiled Categories).
    Returns list of (record_id, path_name) tuples.
    """
    data = open(filepath, 'rb').read()
    pos = 0
    records = []
    while pos + 6 <= len(data):
        record_id = struct.unpack_from('<I', data, pos)[0]
        if record_id == 0xFFFFFFFF:
            break
        name_len = struct.unpack_from('<H', data, pos + 4)[0]
        if pos + 6 + name_len > len(data):
            break
        name_raw = data[pos + 6:pos + 6 + name_len]
        name = xor_decode(name_raw)
        records.append((record_id, name))
        pos += 6 + name_len
    return records


def parse_dpe(dpe_filepath, dpc_records):
    """
    Parse a .dpe file (Database Pre-compiled Elements/Templates).

    DPC record_id values are byte offsets into the DPE file. At each offset:
      [uint16 field1]  — typically 770 (0x0302), 768 for some fields
      [uint16 field2]  — always 0
      TEMPLATE VALUES until 0xFFFF:
        [uint16 length]  — value length (0xFFFF = end)
        [char[length] value]  — XOR 0xFF encoded (Shift-JIS)

    Args:
        dpe_filepath: Path to the .dpe file
        dpc_records: List of (record_id, path_name) from parse_dpc()

    Returns:
        List of dicts: [{"path": str, "field1": int, "field2": int, "templates": [str, ...]}]
    """
    data = open(dpe_filepath, 'rb').read()
    results = []

    for record_id, path_name in dpc_records:
        pos = record_id
        if pos + 4 > len(data):
            results.append({'path': path_name, 'field1': 0, 'field2': 0, 'templates': []})
            continue

        field1 = struct.unpack_from('<H', data, pos)[0]
        field2 = struct.unpack_from('<H', data, pos + 2)[0]
        pos += 4

        templates = []
        while pos + 2 <= len(data):
            val_len = struct.unpack_from('<H', data, pos)[0]
            pos += 2

            if val_len == 0xFFFF:
                break
            if val_len == 0 or val_len > 2000:
                break
            if pos + val_len > len(data):
                break

            val_raw = data[pos:pos + val_len]
            val = xor_decode(val_raw)
            templates.append(val)
            pos += val_len

        results.append({
            'path': path_name,
            'field1': field1,
            'field2': field2,
            'templates': templates,
        })

    return results


def parse_udb(filepath):
    """
    Parse a .udb file (IDEA-encrypted User DataBase).
    Returns list of dicts: [{"path": str, "elements": [{"value": str, "timestamp": str}]}]
    """
    raw = open(filepath, 'rb').read()
    data = decrypt_udb(raw)
    return parse_udb_plaintext(data)


def parse_udb_plaintext(data):
    """Parse decrypted UDB plaintext into structured records."""
    pos = 0
    records = []

    while pos + 4 <= len(data):
        name_len = struct.unpack_from('<I', data, pos)[0]
        pos += 4

        if name_len == 0xFFFFFFFF or name_len == 0xFFFF:
            break
        if name_len == 0 or name_len > 1000:
            break
        if pos + name_len > len(data):
            break

        # Read XOR-encoded path name
        name_raw = data[pos:pos + name_len]
        path = xor_decode(name_raw)
        pos += name_len

        # Read elements until 0xFFFF
        elements = []
        while pos + 2 <= len(data):
            elem_len = struct.unpack_from('<H', data, pos)[0]
            pos += 2

            if elem_len == 0xFFFF:
                break
            if elem_len == 0 or elem_len > 1000:
                break
            if pos + elem_len + 15 > len(data):
                break

            # Read XOR-encoded value
            val_raw = data[pos:pos + elem_len]
            value = xor_decode(val_raw)
            pos += elem_len

            # Read 15-byte timestamp
            ts_raw = data[pos:pos + 15]
            timestamp = ts_raw.decode('ascii', errors='replace').rstrip('\x00')
            pos += 15

            elements.append({
                'value': value,
                'timestamp': timestamp,
            })

        records.append({
            'path': path,
            'elements': elements,
        })

    return records


def build_tree(records):
    """
    Convert flat record list into a nested tree structure.
    Each node: {"name": str, "path": str, "value": str|None, "timestamp": str|None, "children": dict}
    """
    root = {"name": "", "path": "", "value": None, "timestamp": None, "children": {}}

    for rec in records:
        path = rec['path']
        parts = path.split('\\')

        node = root
        for part in parts:
            if part not in node['children']:
                child_path = node['path'] + ('\\' if node['path'] else '') + part
                node['children'][part] = {
                    "name": part,
                    "path": child_path,
                    "value": None,
                    "timestamp": None,
                    "children": {},
                }
            node = node['children'][part]

        # Store value from elements (typically just one element per leaf)
        if rec['elements']:
            node['value'] = rec['elements'][0]['value']
            node['timestamp'] = rec['elements'][0]['timestamp']
            # Store additional elements if any (log entries)
            if len(rec['elements']) > 1:
                node['extra_elements'] = rec['elements'][1:]

    return root


def serialize_udb_plaintext(records):
    """
    Serialize records back to UDB plaintext format.
    Input: list of dicts from parse_udb_plaintext format.
    """
    output = bytearray()

    for rec in records:
        path = rec['path']
        path_encoded = xor_encode(path)

        # Write name_length (uint32 LE)
        output += struct.pack('<I', len(path_encoded))
        # Write XOR-encoded path
        output += path_encoded

        # Write elements
        for elem in rec['elements']:
            value_encoded = xor_encode(elem['value'])
            # Write element length (uint16 LE)
            output += struct.pack('<H', len(value_encoded))
            # Write XOR-encoded value
            output += value_encoded
            # Write 15-byte timestamp (pad with nulls)
            ts = elem['timestamp'].encode('ascii')[:14]
            ts_padded = ts + b'\x00' * (15 - len(ts))
            output += ts_padded

        # Write 0xFFFF terminator
        output += struct.pack('<H', 0xFFFF)

    # Write end-of-file markers (matching game: 4 bytes 0xFF + 10 bytes 0xFF)
    output += b'\xff' * 4
    output += b'\xff' * 10

    return bytes(output)


def save_udb(filepath, records):
    """Save records to an IDEA-encrypted .udb file."""
    plaintext = serialize_udb_plaintext(records)
    encrypted = encrypt_udb(plaintext)
    with open(filepath, 'wb') as f:
        f.write(encrypted)


# ── CLI ──────────────────────────────────────────────────────────────────────

def dump_udb(filepath):
    """Dump a .udb file to stdout."""
    records = parse_udb(filepath)
    for rec in records:
        if rec['elements']:
            for elem in rec['elements']:
                ts = elem['timestamp'] if elem['timestamp'] else ''
                print("  {0} = {1!r}  [{2}]".format(rec['path'], elem['value'], ts))
        else:
            print("  {0}  (no value)".format(rec['path']))
    print("\nTotal: {0} records".format(len(records)))
    return records


def dump_dpc(filepath):
    """Dump a .dpc file to stdout."""
    records = parse_dpc(filepath)
    for rid, name in records:
        print("  [{0:6d}] {1}".format(rid, name))
    print("\nTotal: {0} records".format(len(records)))
    return records


def dump_dpe(dpe_filepath, dpc_filepath):
    """Dump a .dpe file (using paired .dpc for offsets) to stdout."""
    dpc_records = parse_dpc(dpc_filepath)
    dpe_records = parse_dpe(dpe_filepath, dpc_records)
    for rec in dpe_records:
        templates_str = ', '.join(repr(t) for t in rec['templates']) if rec['templates'] else '(none)'
        print("  {0}  [{1}]: {2}".format(rec['path'], len(rec['templates']), templates_str))
    print("\nTotal: {0} variables, {1} template values".format(
        len(dpe_records),
        sum(len(r['templates']) for r in dpe_records)))
    return dpe_records


if __name__ == '__main__':
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    base = str(resolve_seamail_root().parent)

    print("=" * 60)
    print("Seaman.udb (main save)")
    print("=" * 60)
    recs = dump_udb(os.path.join(base, 'SeaMail', 'hostDB', 'Seaman.udb'))

    print("\n" + "=" * 60)
    print("User.udb")
    print("=" * 60)
    dump_udb(os.path.join(base, 'SeaMail', 'hostDB', 'User.udb'))

    print("\n" + "=" * 60)
    print("Calender.udb")
    print("=" * 60)
    dump_udb(os.path.join(base, 'SeaMail', 'hostDB', 'Calender.udb'))
