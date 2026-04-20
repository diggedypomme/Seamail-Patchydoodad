"""
Launcher entry point for the Surgical Patcher.
Starts the seaman_patcher Flask app on port 5005.
"""
import sys
import os
from pathlib import Path

# seaman_patcher/ lives at the repo root, four levels up from this file
# (patcher/ -> seaman_suite/ -> packages/ -> launcher/ -> repo_root/)
PATCHER_DIR = str(Path(__file__).resolve().parents[4] / "seaman_patcher")

if not os.path.isdir(PATCHER_DIR):
    print(f"ERROR: seaman_patcher not found at: {PATCHER_DIR}")
    sys.exit(1)

sys.path.insert(0, PATCHER_DIR)
os.chdir(PATCHER_DIR)

from app import app
print("Surgical Patcher running - open http://127.0.0.1:5005/ or click 'Open' above.")
app.run(debug=False, port=5005)
