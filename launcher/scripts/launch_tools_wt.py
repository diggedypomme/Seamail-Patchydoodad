from __future__ import annotations

from pathlib import Path
import subprocess
import sys


LAUNCHER_ROOT = Path(__file__).resolve().parents[1]
FRIDA_PYTHON = LAUNCHER_ROOT / "venvs" / "launcher-frida" / "Scripts" / "python.exe"
PKG = LAUNCHER_ROOT / "packages" / "seaman_suite"

TABS = [
    ("Menu Overlay",     PKG / "menu_replacement"  / "menu_overlay_v13.py"),
    ("Translation Hook", PKG / "menu_translation"  / "run_menu_translate_v25.py"),
    ("SDP Monitor",      PKG / "comparison_outpt"  / "monitor_sdp_comparisons_v8.py"),
    ("Fix Loop",         PKG / "fix_loop"           / "run_fix_v33.py"),
]


def main() -> int:
    if not FRIDA_PYTHON.exists():
        print(f"Frida venv not found at {FRIDA_PYTHON}", flush=True)
        print("Run 'Setup Env' on any Frida task first.", flush=True)
        return 1

    missing = [str(s) for _, s in TABS if not s.exists()]
    if missing:
        for path in missing:
            print(f"Script not found: {path}", flush=True)
        return 1

    parts = []
    for title, script in TABS:
        cwd = script.parent
        parts.append(f'new-tab --startingDirectory "{cwd}" --title "{title}" cmd /k "{FRIDA_PYTHON}" "{script}"')

    wt_cmd = "wt " + " ; ".join(parts)
    print(f"Opening Windows Terminal with {len(TABS)} tabs...", flush=True)
    subprocess.Popen(wt_cmd, shell=True)
    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
