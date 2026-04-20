"""Launcher wrapper — runs win11_tracker.py using the currently configured game EXE."""
import subprocess
import sys
import os
import json
from pathlib import Path

TRACKER = Path(__file__).resolve().parent / "win11_tracker.py"
CONFIG_PATH = Path(__file__).resolve().parents[4] / "launcher" / "config.json"

if not os.path.exists(TRACKER):
    print(f"ERROR: win11_tracker.py not found at: {TRACKER}")
    sys.exit(1)

# Read the configured game executable name
process_name = "Seaman.exe"  # fallback
try:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    exe_path = config.get("game_executable", "")
    exe_name = os.path.basename(exe_path)
    if exe_name:
        process_name = exe_name
except Exception:
    pass

print(f"Attaching to process: {process_name}")
subprocess.run([sys.executable, TRACKER, f"--process={process_name}"] + sys.argv[1:])
