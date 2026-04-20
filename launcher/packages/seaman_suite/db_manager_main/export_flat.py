"""
export_flat.py — Export all UDB and DPC databases to flat readable text files.

Outputs:
  db_editor/dump/Seaman_udb.txt
  db_editor/dump/User_udb.txt
  db_editor/dump/Calender_udb.txt
  db_editor/dump/SeamanPC_dpc.txt
  db_editor/dump/User_dpc.txt
  db_editor/dump/Relation_dpc.txt
  db_editor/dump/Schedule_dpc.txt
  db_editor/dump/PersonalCalendar_dpc.txt
  db_editor/dump/LargeSchedule_dpc.txt
"""

import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)

from db_parser import parse_udb, parse_dpc, parse_dpe
from path_helpers import resolve_hostdb_dir, resolve_resource_dir

BASE = os.path.dirname(os.path.abspath(__file__))
HOSTDB = str(resolve_hostdb_dir())
RESOURCE = str(resolve_resource_dir())
DUMP = os.path.join(BASE, 'dump')

os.makedirs(DUMP, exist_ok=True)


def export_udb(name, filepath):
    """Export a UDB file to human-readable text."""
    outpath = os.path.join(DUMP, name.replace('.', '_') + '.txt')
    records = parse_udb(filepath)

    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(f"# {name} — Seaman PC Database Dump\n")
        f.write(f"# Source: {filepath}\n")
        f.write(f"# Records: {len(records)}\n")
        f.write(f"# Format: path = value  [timestamp]\n")
        f.write(f"#   (no value) = node exists but has no data\n")
        f.write(f"#   Multiple lines with same path = history log (newest first)\n")
        f.write("#\n\n")

        for rec in records:
            if rec['elements']:
                for elem in rec['elements']:
                    ts = elem['timestamp'] if elem['timestamp'] else ''
                    f.write(f"{rec['path']} = {elem['value']}  [{ts}]\n")
            else:
                f.write(f"{rec['path']}  (no value)\n")

        f.write(f"\n# Total: {len(records)} records\n")

    values_with_data = sum(1 for r in records if r['elements'])
    print(f"  {name} -> {outpath} ({len(records)} records, {values_with_data} with values)")


def export_dpc(name, filepath):
    """Export a DPC file to human-readable text."""
    outpath = os.path.join(DUMP, name.replace('.', '_') + '.txt')
    records = parse_dpc(filepath)

    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(f"# {name} — Variable Path Templates\n")
        f.write(f"# Source: {filepath}\n")
        f.write(f"# Paths: {len(records)}\n")
        f.write(f"# Format: [record_id] path\n")
        f.write("#\n\n")

        for rid, path in records:
            f.write(f"[{rid:6d}] {path}\n")

        f.write(f"\n# Total: {len(records)} paths\n")

    print(f"  {name} -> {outpath} ({len(records)} paths)")


def export_dpe(dpc_name, dpc_filepath, dpe_filepath):
    """Export a DPE file (with its paired DPC) to human-readable text."""
    base_name = dpc_name.replace('.dpc', '')
    outpath = os.path.join(DUMP, base_name + '_dpe.txt')
    dpc_records = parse_dpc(dpc_filepath)
    dpe_records = parse_dpe(dpe_filepath, dpc_records)

    total_templates = sum(len(r['templates']) for r in dpe_records)
    multi_value = sum(1 for r in dpe_records if len(r['templates']) > 1)

    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(f"# {base_name}.dpe — Template Values (Valid Enum Values per Variable)\n")
        f.write(f"# DPE source: {dpe_filepath}\n")
        f.write(f"# DPC source: {dpc_filepath}\n")
        f.write(f"# Variables: {len(dpe_records)}\n")
        f.write(f"# Total template values: {total_templates}\n")
        f.write(f"# Variables with multiple values: {multi_value}\n")
        f.write(f"# Format: path [count]: [0] value0, [1] value1, ...\n")
        f.write("#\n\n")

        for rec in dpe_records:
            count = len(rec['templates'])
            if count == 0:
                f.write(f"{rec['path']} [0]: (none)\n")
            elif count == 1:
                f.write(f"{rec['path']} [1]: {rec['templates'][0]}\n")
            else:
                vals = ', '.join(f"[{i}] {v}" for i, v in enumerate(rec['templates']))
                f.write(f"{rec['path']} [{count}]: {vals}\n")

        f.write(f"\n# Total: {len(dpe_records)} variables, {total_templates} template values\n")

    print(f"  {base_name}.dpe -> {outpath} ({len(dpe_records)} vars, {total_templates} templates)")


# ── Main ──────────────────────────────────────────────────────────────────────

print("Exporting UDB files...")
for name, path in [
    ('Seaman.udb', os.path.join(HOSTDB, 'Seaman.udb')),
    ('User.udb', os.path.join(HOSTDB, 'User.udb')),
    ('Calender.udb', os.path.join(HOSTDB, 'Calender.udb')),
]:
    if os.path.exists(path):
        export_udb(name, path)
    else:
        print(f"  SKIP: {path} not found")

DPC_DPE_PAIRS = [
    ('SeamanPC.dpc', os.path.join(RESOURCE, 'SeamanPC.dpc'), os.path.join(RESOURCE, 'SeamanPC.dpe')),
    ('User.dpc', os.path.join(RESOURCE, 'User.dpc'), os.path.join(RESOURCE, 'User.dpe')),
    ('Relation.dpc', os.path.join(RESOURCE, 'Relation.dpc'), os.path.join(RESOURCE, 'Relation.dpe')),
    ('Schedule.dpc', os.path.join(RESOURCE, 'Schedule.dpc'), os.path.join(RESOURCE, 'Schedule.dpe')),
    ('PersonalCalendar.dpc', os.path.join(RESOURCE, 'PersonalCalendar.dpc'), os.path.join(RESOURCE, 'PersonalCalendar.dpe')),
    ('LargeSchedule.dpc', os.path.join(RESOURCE, 'LargeSchedule.dpc'), os.path.join(RESOURCE, 'LargeSchedule.dpe')),
]

print("\nExporting DPC files...")
for name, dpc_path, dpe_path in DPC_DPE_PAIRS:
    if os.path.exists(dpc_path):
        export_dpc(name, dpc_path)
    else:
        print(f"  SKIP: {dpc_path} not found")

print("\nExporting DPE template files...")
for name, dpc_path, dpe_path in DPC_DPE_PAIRS:
    if os.path.exists(dpc_path) and os.path.exists(dpe_path):
        export_dpe(name, dpc_path, dpe_path)
    else:
        missing = dpe_path if not os.path.exists(dpe_path) else dpc_path
        print(f"  SKIP: {missing} not found")

print(f"\nAll exports written to: {DUMP}")
