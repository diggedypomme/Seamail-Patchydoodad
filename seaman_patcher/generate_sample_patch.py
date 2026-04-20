import json
from core.patch_engine import PatchEngine

ORIGINAL = r"C:\2026_projects\ghi\SeaMail\Seaman_1_2_57.exe"
MODIFIED = r"C:\2026_projects\ghi\SeaMail\Seaman_fully_patched.exe"
OUTPUT = r"C:\2026_projects\ghi\seaman_patcher\patches\screensaver_and_menu_fixes.json"

def main():
    print(f"[*] Comparing:\n    {ORIGINAL}\n    {MODIFIED}")
    
    try:
        patch = PatchEngine.generate_patch(
            ORIGINAL, 
            MODIFIED, 
            "Screensaver & Global Fixes", 
            "Includes the screensaver timeout bypass and various stability patches from the 'fully_patched' build."
        )
        
        with open(OUTPUT, "w") as f:
            json.dump(patch, f, indent=4)
            
        print(f"[+] Patch generated: {OUTPUT}")
        print(f"[+] Found {len(patch['patches'])} modified hunks.")
        
    except Exception as e:
        print(f"[!] Error: {e}")

if __name__ == "__main__":
    main()
