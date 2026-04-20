from __future__ import annotations

from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUITE_ROOT = PROJECT_ROOT / "packages" / "seaman_suite"
if str(SUITE_ROOT) not in sys.path:
    sys.path.insert(0, str(SUITE_ROOT))

from path_helpers import resolve_game_executable, resolve_seamail_root  # noqa: E402


def main() -> int:
    game_executable = resolve_game_executable()
    seamail_root = resolve_seamail_root()
    launch_target = game_executable.resolve(strict=False)

    print(f"Launching executable: {launch_target}", flush=True)
    if not game_executable.exists():
        print("Game executable does not exist. Update the launcher settings first.", flush=True)
        return 1

    print(f"Launching game from: {seamail_root}", flush=True)
    process = subprocess.Popen(
        [str(launch_target)],
        cwd=str(launch_target.parent),
    )
    print(f"Game process started with pid {process.pid}", flush=True)
    return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
