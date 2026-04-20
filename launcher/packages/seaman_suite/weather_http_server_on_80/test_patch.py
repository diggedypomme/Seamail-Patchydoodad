#!/usr/bin/env python3
"""
Test if WeatherGet.dll has been patched correctly
"""

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from path_helpers import resolve_weather_dll

def check_dll_patch(dll_path):
    """Check if DLL is patched to localhost"""

    dll_path = Path(dll_path)

    if not dll_path.exists():
        print(f"❌ DLL not found: {dll_path}")
        return False

    with open(dll_path, 'rb') as f:
        data = f.read()

    # Check for original URL
    original = b'http://www.jma.go.jp/JMA_HP/jp/'
    patched = b'http://localhost:8080/JMA_HP/jp/'

    has_original = original in data
    has_patched = patched in data

    print(f"DLL Check: {dll_path}")
    print(f"-" * 60)

    if has_original and not has_patched:
        print(f"⚠️  Status: ORIGINAL (not patched)")
        print(f"    Contains: http://www.jma.go.jp/JMA_HP/jp/")
        print(f"")
        print(f"Run: python patch_weather_dll.py")
        return False

    elif has_patched and not has_original:
        print(f"✅ Status: PATCHED")
        print(f"    Points to: http://localhost:8080/JMA_HP/jp/")
        print(f"")
        print(f"Ready to use with weather server!")
        return True

    elif has_original and has_patched:
        print(f"⚠️  Status: AMBIGUOUS (contains both URLs)")
        print(f"    This is unusual - DLL may have multiple URL references")
        return True

    else:
        print(f"❌ Status: UNKNOWN")
        print(f"    Neither original nor patched URL found")
        print(f"    DLL may have different URL structure")
        return False


def check_backup(dll_path):
    """Check if backup exists"""
    dll_path = Path(dll_path)
    backup_path = dll_path.with_suffix('.dll.bak')

    print(f"")
    print(f"Backup Check:")
    print(f"-" * 60)

    if backup_path.exists():
        print(f"✅ Backup exists: {backup_path}")
        print(f"    You can restore with: python patch_weather_dll.py restore")
        return True
    else:
        print(f"⚠️  No backup found")
        print(f"    Backup will be created on first patch")
        return False


if __name__ == '__main__':
    import sys

    dll_path = str(resolve_weather_dll())
    if len(sys.argv) > 1:
        dll_path = sys.argv[1]

    print("="*60)
    print("WeatherGet.dll Patch Checker")
    print("="*60)
    print()

    check_dll_patch(dll_path)
    check_backup(dll_path)

    print()
    print("="*60)
