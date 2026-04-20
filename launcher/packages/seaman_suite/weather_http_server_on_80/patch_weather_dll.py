#!/usr/bin/env python3
"""
Patch WeatherGet.dll to redirect to localhost weather server
Replaces: http://www.jma.go.jp/JMA_HP/jp/
With:     http://localhost:8080/JMA_HP/jp/
"""

import sys
import shutil
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from path_helpers import resolve_weather_dll

def patch_weather_dll(dll_path, backup=True):
    """
    Patch the WeatherGet.dll URL to point to localhost.

    Args:
        dll_path: Path to WeatherGet.dll
        backup: Create backup before patching (default True)
    """

    dll_path = Path(dll_path)

    if not dll_path.exists():
        print(f"ERROR: DLL not found at {dll_path}")
        return False

    # Create backup
    if backup:
        backup_path = dll_path.with_suffix('.dll.bak')
        if not backup_path.exists():
            shutil.copy2(dll_path, backup_path)
            print(f"✓ Backup created: {backup_path}")
        else:
            print(f"✓ Backup already exists: {backup_path}")

    # Read DLL
    with open(dll_path, 'rb') as f:
        data = bytearray(f.read())

    # Original URL (null-terminated)
    original_url = b'http://www.jma.go.jp/JMA_HP/jp/\x00'

    # New URL (must be same length or shorter!)
    # 127.0.0.1 is 9 chars vs 192.168.0.6 which is 11 chars. BOTH FIT.
    new_url = b'http://127.0.0.1/JMA_HP/jp/\x00'

    # Make sure new URL fits in same space
    if len(new_url) > len(original_url):
        print(f"ERROR: New URL too long ({len(new_url)} > {len(original_url)})")
        return False

    # Pad with nulls if shorter
    new_url = new_url.ljust(len(original_url), b'\x00')

    # Find and replace
    offset = data.find(original_url)

    if offset == -1:
        print(f"ERROR: Original URL not found in DLL!")
        print(f"Searched for: {original_url}")
        print(f"This DLL may already be patched or have a different URL structure.")
        return False

    print(f"✓ Found original URL at offset 0x{offset:X}")
    print(f"  Original: {original_url.decode('ascii', errors='ignore')}")
    print(f"  New:      {new_url.decode('ascii', errors='ignore')}")

    # Apply patch
    data[offset:offset+len(new_url)] = new_url

    # Write patched DLL
    with open(dll_path, 'wb') as f:
        f.write(data)

    print(f"✓ DLL patched successfully!")
    print(f"")
    print(f"Next steps:")
    print(f"  1. Start weather server on 127.0.0.1:80 (Port 80)")
    print(f"  2. Run as admin: python weather_mock.py 80")
    print(f"  3. Launch Seaman PC (on same machine or using bridge)")
    print(f"  4. Trigger weather fetch (game should do this automatically)")
    print(f"  5. Check database proxy for variable writes")

    return True


def restore_backup(dll_path):
    """Restore DLL from backup"""
    dll_path = Path(dll_path)
    backup_path = dll_path.with_suffix('.dll.bak')

    if not backup_path.exists():
        print(f"ERROR: No backup found at {backup_path}")
        return False

    shutil.copy2(backup_path, dll_path)
    print(f"✓ DLL restored from backup")
    return True


if __name__ == '__main__':
    print("="*60)
    print("WeatherGet.dll Patcher for Seaman PC")
    print("="*60)

    if len(sys.argv) > 1 and sys.argv[1] == 'restore':
        dll_path = str(resolve_weather_dll())
        if len(sys.argv) > 2:
            dll_path = sys.argv[2]
        restore_backup(dll_path)
    else:
        dll_path = str(resolve_weather_dll())
        if len(sys.argv) > 1:
            dll_path = sys.argv[1]

        print(f"Target DLL: {dll_path}")
        print(f"")

        patch_weather_dll(dll_path)

    print("="*60)
