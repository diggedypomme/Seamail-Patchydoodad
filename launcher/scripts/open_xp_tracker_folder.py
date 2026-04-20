import os
from pathlib import Path

folder = Path(__file__).resolve().parents[1] / "packages" / "seaman_suite" / "position_tracker_bridge" / "xp_build"
os.startfile(str(folder))
