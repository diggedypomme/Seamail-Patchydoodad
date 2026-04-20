from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path
import argparse
import json
import os
import signal
import subprocess
import sys
import threading


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def log_line(log_path: Path, stream: str, text: str) -> None:
    clean = text.rstrip()
    if not clean:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{utc_now()}] [{stream}] {clean}\n")


def write_state(state_path: Path, payload: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_background(args: argparse.Namespace) -> int:
    command = [args.python_bin, args.script_path, *args.script_args]
    log_path = Path(args.log_path)
    state_path = Path(args.state_path)
    cwd = args.cwd

    log_line(log_path, "system", f"Elevated helper starting: {' '.join(command)}")
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    write_state(
        state_path,
        {
            "status": "running",
            "pid": process.pid,
            "started_at": utc_now(),
            "finished_at": None,
            "exit_code": None,
            "last_error": None,
            "launch_mode": "background",
            "requires_admin": True,
        },
    )
    log_line(log_path, "system", f"Elevated process pid {process.pid} started.")

    def forward(stream, stream_name: str) -> None:
        try:
            for line in iter(stream.readline, ""):
                log_line(log_path, stream_name, line)
        finally:
            stream.close()

    if process.stdout is not None:
        threading.Thread(target=forward, args=(process.stdout, "stdout"), daemon=True).start()
    if process.stderr is not None:
        threading.Thread(target=forward, args=(process.stderr, "stderr"), daemon=True).start()

    return_code = process.wait()
    status = "completed" if return_code == 0 and args.kind == "oneshot" else ("idle" if return_code == 0 else "failed")
    write_state(
        state_path,
        {
            "status": status,
            "pid": None,
            "started_at": None,
            "finished_at": utc_now(),
            "exit_code": return_code,
            "last_error": None if return_code == 0 else f"Process exited with code {return_code}",
            "launch_mode": "background",
            "requires_admin": True,
        },
    )
    log_line(log_path, "system", f"Elevated process exited with code {return_code}.")
    return return_code


def run_console(args: argparse.Namespace) -> int:
    log_path = Path(args.log_path)
    state_path = Path(args.state_path)
    comspec = os.environ.get("COMSPEC", "cmd.exe")
    script_command = subprocess.list2cmdline([args.python_bin, args.script_path, *args.script_args])
    command = [comspec, "/k", script_command]
    log_line(log_path, "system", f"Opening elevated console task in its own CMD window: {script_command}")
    process = subprocess.Popen(
        command,
        cwd=args.cwd,
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
    )
    write_state(
        state_path,
        {
            "status": "running",
            "pid": process.pid,
            "started_at": utc_now(),
            "finished_at": None,
            "exit_code": None,
            "last_error": None,
            "launch_mode": "console",
            "requires_admin": True,
        },
    )
    log_line(log_path, "system", f"Elevated console process pid {process.pid} started.")
    return_code = process.wait()
    status = "completed" if return_code == 0 and args.kind == "oneshot" else ("idle" if return_code == 0 else "failed")
    write_state(
        state_path,
        {
            "status": status,
            "pid": None,
            "started_at": None,
            "finished_at": utc_now(),
            "exit_code": return_code,
            "last_error": None if return_code == 0 else f"Process exited with code {return_code}",
            "launch_mode": "console",
            "requires_admin": True,
        },
    )
    log_line(log_path, "system", f"Elevated console task exited with code {return_code}.")
    return return_code


def stop_process(args: argparse.Namespace) -> int:
    log_path = Path(args.log_path)
    state_path = Path(args.state_path)
    pid = int(args.pid)
    log_line(log_path, "system", f"Stopping elevated pid {pid}.")
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=True, capture_output=True, text=True)
        else:
            os.kill(pid, signal.SIGTERM)
        result_error = None
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        combined = f"{stdout}\n{stderr}".strip().lower()
        if "not found" in combined or "no running instance" in combined or "not running" in combined:
            result_error = None
            log_line(log_path, "system", f"Elevated pid {pid} was already gone.")
        else:
            log_line(log_path, "system", f"Failed to stop elevated pid {pid}: {exc}")
            return 1
    except ProcessLookupError:
        result_error = None
        log_line(log_path, "system", f"Elevated pid {pid} was already gone.")
    except Exception as exc:
        log_line(log_path, "system", f"Failed to stop elevated pid {pid}: {exc}")
        return 1

    write_state(
        state_path,
        {
            "status": "stopped",
            "pid": None,
            "started_at": None,
            "finished_at": utc_now(),
            "exit_code": None,
            "last_error": result_error,
            "launch_mode": args.mode,
            "requires_admin": True,
        },
    )
    log_line(log_path, "system", f"Elevated pid {pid} stopped.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=["start", "stop"], required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--mode", choices=["background", "console"], required=True)
    parser.add_argument("--kind", default="service")
    parser.add_argument("--python-bin", required=False)
    parser.add_argument("--script-path", required=False)
    parser.add_argument("--cwd", required=False)
    parser.add_argument("--log-path", required=True)
    parser.add_argument("--state-path", required=True)
    parser.add_argument("--pid", required=False)
    parser.add_argument("script_args", nargs="*")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.action == "stop":
        return stop_process(args)
    if args.mode == "console":
        return run_console(args)
    return run_background(args)


if __name__ == "__main__":
    raise SystemExit(main())
