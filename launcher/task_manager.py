import csv
from collections import deque
from datetime import datetime, UTC
from pathlib import Path
import ctypes
import json
import os
import shutil
import subprocess
import sys
import threading


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def is_process_elevated() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


class TaskManager:
    def __init__(self, tasks: dict[str, dict], log_root: Path, venv_manager=None) -> None:
        self.tasks = tasks
        self.log_root = log_root
        self.venv_manager = venv_manager
        self.log_root.mkdir(parents=True, exist_ok=True)
        self.dump_root = self.log_root.parent / "log_dump"
        self.dump_root.mkdir(parents=True, exist_ok=True)
        self._archive_existing_logs()
        self.state_root = self.log_root.parent / "task_state"
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.state_dump_root = self.log_root.parent / "task_state_dump"
        self.state_dump_root.mkdir(parents=True, exist_ok=True)
        self._archive_existing_state()
        self._lock = threading.RLock()
        self._buffers = {task_id: deque(maxlen=400) for task_id in tasks}
        self._cursors = {task_id: 0 for task_id in tasks}
        self._file_offsets = {task_id: 0 for task_id in tasks}
        self._processes: dict[str, subprocess.Popen | None] = {task_id: None for task_id in tasks}
        self._stop_requested = {task_id: False for task_id in tasks}
        self._state = {
            task_id: {
                "status": "unavailable" if not task["available"] else "idle",
                "pid": None,
                "started_at": None,
                "finished_at": None,
                "exit_code": None,
                "last_error": None,
                "last_log_path": str(self._log_path(task_id)),
            }
            for task_id, task in tasks.items()
        }

    def _archive_existing_logs(self) -> None:
        log_files = sorted(self.log_root.glob("*.log"))
        if not log_files:
            return

        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        dump_dir = self.dump_root / stamp
        dump_dir.mkdir(parents=True, exist_ok=True)

        for log_file in log_files:
            destination = dump_dir / log_file.name
            if destination.exists():
                destination.unlink()
            shutil.move(str(log_file), str(destination))

    def _archive_existing_state(self) -> None:
        state_files = sorted(self.state_root.glob("*.json"))
        if not state_files:
            return

        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        dump_dir = self.state_dump_root / stamp
        dump_dir.mkdir(parents=True, exist_ok=True)

        for state_file in state_files:
            destination = dump_dir / state_file.name
            if destination.exists():
                destination.unlink()
            shutil.move(str(state_file), str(destination))

    def _log_path(self, task_id: str) -> Path:
        return self.log_root / f"{task_id}.log"

    def _resolve_script_path(self, task: dict) -> Path:
        script_path = Path(task["script_path"])
        if not script_path.is_absolute():
            script_path = Path(__file__).resolve().parent.parent / script_path
        return script_path

    def _state_path(self, task_id: str) -> Path:
        return self.state_root / f"{task_id}.json"

    def _helper_script_path(self) -> Path:
        return Path(__file__).resolve().parent / "scripts" / "elevated_task_runner.py"

    def _game_image_name(self) -> str | None:
        try:
            from packages.seaman_suite.path_helpers import resolve_game_executable
        except Exception:
            return None

        try:
            return resolve_game_executable().name
        except Exception:
            return None

    def _windows_process_rows(self, image_name: str) -> list[dict[str, str]]:
        if os.name != "nt" or not image_name:
            return []
        try:
            completed = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH", "/FI", f"IMAGENAME eq {image_name}"],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception:
            return []

        rows: list[dict[str, str]] = []
        for row in csv.reader(completed.stdout.splitlines()):
            if len(row) < 2:
                continue
            if row[0].lower() == "info:":
                continue
            rows.append(
                {
                    "image_name": row[0],
                    "pid": row[1],
                }
            )
        return rows

    def _merge_live_game_state(self, task_id: str, state: dict) -> None:
        if task_id != "launch_game":
            return

        image_name = self._game_image_name()
        rows = self._windows_process_rows(image_name or "")
        if rows:
            state["status"] = "running"
            state["pid"] = int(rows[0]["pid"])
            state["exit_code"] = None
            state["last_error"] = None
        elif self._processes[task_id] is None:
            state["status"] = "idle"
            state["pid"] = None

    def _append_log(self, task_id: str, stream: str, text: str) -> None:
        clean = text.rstrip()
        if not clean:
            return

        with self._lock:
            self._cursors[task_id] += 1
            entry = {
                "id": self._cursors[task_id],
                "stream": stream,
                "text": clean,
                "timestamp": utc_now(),
            }
            self._buffers[task_id].append(entry)

            with self._log_path(task_id).open("a", encoding="utf-8") as handle:
                handle.write(f"[{entry['timestamp']}] [{stream}] {clean}\n")
                self._file_offsets[task_id] = handle.tell()

    def _sync_buffer_from_file(self, task_id: str) -> None:
        log_path = self._log_path(task_id)
        if not log_path.exists():
            return

        with self._lock:
            offset = self._file_offsets.get(task_id, 0)
            with log_path.open("r", encoding="utf-8") as handle:
                handle.seek(offset)
                chunk = handle.read()
                self._file_offsets[task_id] = handle.tell()

            if not chunk:
                return

            for raw_line in chunk.splitlines():
                line = raw_line.rstrip()
                if not line:
                    continue
                timestamp = utc_now()
                stream = "system"
                text = line
                if line.startswith("[") and "] [" in line:
                    first_end = line.find("]")
                    second_start = line.find("[", first_end + 1)
                    second_end = line.find("]", second_start + 1)
                    if first_end != -1 and second_start != -1 and second_end != -1:
                        timestamp = line[1:first_end]
                        stream = line[second_start + 1:second_end]
                        text = line[second_end + 2:]

                self._cursors[task_id] += 1
                self._buffers[task_id].append(
                    {
                        "id": self._cursors[task_id],
                        "stream": stream,
                        "text": text,
                        "timestamp": timestamp,
                    }
                )

    def _load_external_state(self, task_id: str) -> dict | None:
        state_path = self._state_path(task_id)
        if not state_path.exists():
            return None
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _merge_external_state(self, task_id: str, state: dict) -> None:
        if self._processes[task_id] is not None:
            return
        external = self._load_external_state(task_id)
        if not external:
            return
        state["status"] = external.get("status", state["status"])
        state["pid"] = external.get("pid", state["pid"])
        state["started_at"] = external.get("started_at", state["started_at"])
        state["finished_at"] = external.get("finished_at", state["finished_at"])
        state["exit_code"] = external.get("exit_code", state["exit_code"])
        state["last_error"] = external.get("last_error", state["last_error"])

    def _shell_execute_runas(self, arguments: list[str], cwd: Path) -> tuple[bool, str | None]:
        params = subprocess.list2cmdline(arguments)
        rc = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            params,
            str(cwd),
            1,
        )
        if rc <= 32:
            if rc == 5:
                return False, "Access was denied while requesting elevation."
            if rc == 1223:
                return False, "UAC prompt was cancelled."
            return False, f"Elevation launch failed with code {rc}."
        return True, None

    def _start_admin_task(self, task_id: str, task: dict, script_path: Path) -> tuple[bool, dict, int]:
        helper_path = self._helper_script_path()
        python_bin = sys.executable
        if self.venv_manager is not None:
            venv_python = self.venv_manager.python_for_task(task)
            if venv_python is not None:
                python_bin = str(venv_python)

        arguments = [
            str(helper_path),
            "--action",
            "start",
            "--task-id",
            task_id,
            "--mode",
            task.get("launch_mode", "background"),
            "--kind",
            task.get("kind", "service"),
            "--python-bin",
            python_bin,
            "--script-path",
            str(script_path),
            "--cwd",
            str(script_path.parent),
            "--log-path",
            str(self._log_path(task_id)),
            "--state-path",
            str(self._state_path(task_id)),
            *task.get("args", []),
        ]

        self._append_log(task_id, "system", f"Requesting admin launch for {task['label']}.")
        ok, error = self._shell_execute_runas(arguments, script_path.parent)
        if not ok:
            self._append_log(task_id, "system", error or "Elevation request failed.")
            return False, {"error": error or "Elevation request failed.", "task": self._snapshot(task_id)}, 400

        self._state[task_id]["status"] = "running"
        self._state[task_id]["pid"] = None
        self._state[task_id]["started_at"] = utc_now()
        self._state[task_id]["finished_at"] = None
        self._state[task_id]["exit_code"] = None
        self._state[task_id]["last_error"] = None
        return True, {"task": self._snapshot(task_id)}, 200

    def _stop_admin_task(self, task_id: str, task: dict) -> tuple[bool, dict, int]:
        external = self._load_external_state(task_id)
        if not external or not external.get("pid"):
            return False, {"error": "Task is not running", "task": self._snapshot(task_id)}, 400

        helper_path = self._helper_script_path()
        arguments = [
            str(helper_path),
            "--action",
            "stop",
            "--task-id",
            task_id,
            "--mode",
            external.get("launch_mode", task.get("launch_mode", "background")),
            "--pid",
            str(external["pid"]),
            "--log-path",
            str(self._log_path(task_id)),
            "--state-path",
            str(self._state_path(task_id)),
        ]

        self._append_log(task_id, "system", f"Requesting admin stop for {task['label']}.")
        ok, error = self._shell_execute_runas(arguments, self._resolve_script_path(task).parent)
        if not ok:
            self._append_log(task_id, "system", error or "Failed to request elevated stop.")
            return False, {"error": error or "Failed to request elevated stop.", "task": self._snapshot(task_id)}, 400

        return True, {"task": self._snapshot(task_id)}, 200

    def _build_command(self, task: dict) -> list[str]:
        script_path = self._resolve_script_path(task)
        python_bin = sys.executable
        if self.venv_manager is not None:
            venv_python = self.venv_manager.python_for_task(task)
            if venv_python is not None:
                python_bin = str(venv_python)
        return [python_bin, "-u", str(script_path), *task.get("args", [])]

    def _build_console_command(self, task: dict) -> list[str]:
        script_path = self._resolve_script_path(task)
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        python_bin = sys.executable
        if self.venv_manager is not None:
            venv_python = self.venv_manager.python_for_task(task)
            if venv_python is not None:
                python_bin = str(venv_python)
        return [comspec, "/k", python_bin, str(script_path), *task.get("args", [])]

    def _snapshot(self, task_id: str) -> dict:
        self._sync_buffer_from_file(task_id)
        task = self.tasks[task_id]
        state = self._state[task_id]
        self._merge_external_state(task_id, state)
        self._merge_live_game_state(task_id, state)
        venv_status = self.venv_manager.status_for_task(task) if self.venv_manager is not None else {
            "required": False,
            "ready": True,
            "exists": False,
            "configured": False,
            "key": None,
            "label": None,
            "path": None,
            "python_path": None,
            "source": None,
        }
        return {
            "id": task["id"],
            "label": task["label"],
            "group": task["group"],
            "description": task["description"],
            "kind": task["kind"],
            "requires_admin": task["requires_admin"],
            "available": task["available"],
            "open_url": task.get("open_url"),
            "launch_mode": task.get("launch_mode", "background"),
            "has_interface": task.get("has_interface", False),
            "interface_key": task.get("interface_key"),
            "interface_label": task.get("interface_label"),
            "interface_mode": task.get("interface_mode", "generic"),
            "conflicts_with": task.get("conflicts_with", []),
            "venv_key": task.get("venv_key"),
            "venv_label": task.get("venv_label"),
            "venv_status": venv_status,
            "can_stop": task.get("can_stop", True),
            "stop_label": task.get("stop_label", "Stop"),
            "script_path": task["script_path"],
            "args": task.get("args", []),
            **state,
        }

    def list_tasks(self, group: str | None = None) -> list[dict]:
        with self._lock:
            task_ids = sorted(self.tasks)
            if group:
                task_ids = [task_id for task_id in task_ids if self.tasks[task_id]["group"] == group]
            return [self._snapshot(task_id) for task_id in task_ids]

    def get_task(self, task_id: str) -> dict | None:
        with self._lock:
            if task_id not in self.tasks:
                return None
            return self._snapshot(task_id)

    def _start_stream_reader(self, task_id: str, stream, stream_name: str) -> None:
        def reader() -> None:
            try:
                for line in iter(stream.readline, ""):
                    self._append_log(task_id, stream_name, line)
            finally:
                stream.close()

        threading.Thread(target=reader, daemon=True).start()

    def _watch_process(self, task_id: str, process: subprocess.Popen) -> None:
        return_code = process.wait()
        with self._lock:
            self._processes[task_id] = None
            self._state[task_id]["pid"] = None
            self._state[task_id]["finished_at"] = utc_now()
            self._state[task_id]["exit_code"] = return_code

            if self._stop_requested[task_id]:
                self._state[task_id]["status"] = "stopped"
                self._stop_requested[task_id] = False
            elif return_code == 0 and self.tasks[task_id]["kind"] == "oneshot":
                self._state[task_id]["status"] = "completed"
            elif return_code == 0:
                self._state[task_id]["status"] = "idle"
            else:
                self._state[task_id]["status"] = "failed"
                self._state[task_id]["last_error"] = f"Process exited with code {return_code}"

    def start_task(self, task_id: str) -> tuple[bool, dict, int]:
        with self._lock:
            if task_id not in self.tasks:
                return False, {"error": "Unknown task"}, 404

            task = self.tasks[task_id]
            external = self._load_external_state(task_id)
            if external and external.get("status") == "running":
                return True, {"task": self._snapshot(task_id)}, 200
            conflicting_ids = [
                other_id
                for other_id in task.get("conflicts_with", [])
                if other_id in self.tasks and self._state[other_id]["status"] == "running"
            ]
            if conflicting_ids:
                conflicting_tasks = [self._snapshot(other_id) for other_id in conflicting_ids]
                conflicting_labels = ", ".join(other_task["label"] for other_task in conflicting_tasks)
                return False, {
                    "error": f"Cannot start {task['label']} while {conflicting_labels} is already running.",
                    "task": self._snapshot(task_id),
                    "conflicting_tasks": conflicting_tasks,
                }, 409

            if not task["available"]:
                return False, {
                    "error": "Task is not wired yet",
                    "task": self._snapshot(task_id),
                }, 400

            if self.venv_manager is not None:
                venv_status = self.venv_manager.status_for_task(task)
                if venv_status["required"] and not venv_status["ready"]:
                    return False, {
                        "error": f"{task['label']} needs its dedicated environment before it can start.",
                        "task": self._snapshot(task_id),
                        "venv": venv_status,
                    }, 400

            script_path = self._resolve_script_path(task)
            print(f"[START] {task_id} | requires_admin={task['requires_admin']} | launch_mode={task.get('launch_mode','background')} | elevated={is_process_elevated()} | script={script_path}")
            if task["requires_admin"]:
                if not is_process_elevated():
                    print(f"[START] {task_id} -> _start_admin_task (UAC)")
                    return self._start_admin_task(task_id, task, script_path)

            if not script_path.exists():
                return False, {
                    "error": f"Script path does not exist: {script_path}",
                    "task": self._snapshot(task_id),
                }, 400

            if self._processes[task_id] is not None:
                return True, {"task": self._snapshot(task_id)}, 200

            log_path = self._log_path(task_id)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self._append_log(task_id, "system", f"Starting task {task['label']}")

            try:
                launch_mode = task.get("launch_mode", "background")
                print(f"[START] {task_id} -> launch_mode={launch_mode}")
                if launch_mode == "console":
                    process = subprocess.Popen(
                        self._build_console_command(task),
                        cwd=str(script_path.parent),
                        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                    )
                    self._append_log(task_id, "system", "Opened in a visible CMD window for interactive use.")
                elif launch_mode == "detached":
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    si.wShowWindow = 2  # SW_SHOWMINIMIZED
                    process = subprocess.Popen(
                        self._build_command(task),
                        cwd=str(script_path.parent),
                        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                        close_fds=True,
                        startupinfo=si,
                    )
                    self._append_log(task_id, "system", "Launched as detached process.")
                else:
                    process = subprocess.Popen(
                        self._build_command(task),
                        cwd=str(script_path.parent),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                    )
            except Exception as exc:
                self._state[task_id]["status"] = "failed"
                self._state[task_id]["last_error"] = str(exc)
                self._append_log(task_id, "system", f"Failed to start: {exc}")
                return False, {"error": str(exc), "task": self._snapshot(task_id)}, 500

            self._processes[task_id] = process
            self._stop_requested[task_id] = False
            self._state[task_id]["status"] = "running"
            self._state[task_id]["pid"] = process.pid
            self._state[task_id]["started_at"] = utc_now()
            self._state[task_id]["finished_at"] = None
            self._state[task_id]["exit_code"] = None
            self._state[task_id]["last_error"] = None

            if process.stdout is not None:
                self._start_stream_reader(task_id, process.stdout, "stdout")
            if process.stderr is not None:
                self._start_stream_reader(task_id, process.stderr, "stderr")

            threading.Thread(target=self._watch_process, args=(task_id, process), daemon=True).start()
            return True, {"task": self._snapshot(task_id)}, 200

    def create_task_venv(self, task_id: str) -> tuple[bool, dict, int]:
        with self._lock:
            if task_id not in self.tasks:
                return False, {"error": "Unknown task"}, 404
            task = self.tasks[task_id]

        if self.venv_manager is None:
            return False, {"error": "Virtual environment manager is not configured."}, 500

        success, payload, status_code = self.venv_manager.create_for_task(task)
        for line in payload.get("log_lines", []):
            self._append_log(task_id, line.get("stream", "system"), line.get("text", ""))
        if "task" not in payload:
            payload["task"] = self.get_task(task_id)
        return success, payload, status_code

    def stop_task(self, task_id: str) -> tuple[bool, dict, int]:
        with self._lock:
            if task_id not in self.tasks:
                return False, {"error": "Unknown task"}, 404

            task = self.tasks[task_id]

            if task["requires_admin"] and not is_process_elevated():
                return self._stop_admin_task(task_id, task)

            process = self._processes[task_id]
            if process is None and task_id == "launch_game" and os.name == "nt":
                image_name = self._game_image_name()
                rows = self._windows_process_rows(image_name or "")
                if not rows:
                    return False, {"error": "Task is not running", "task": self._snapshot(task_id)}, 400

                for row in rows:
                    subprocess.run(
                        ["taskkill", "/PID", row["pid"], "/T", "/F"],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                self._append_log(task_id, "system", f"Stopped running game process(es): {image_name}")
                self._state[task_id]["status"] = "stopped"
                self._state[task_id]["pid"] = None
                self._state[task_id]["finished_at"] = utc_now()
                self._state[task_id]["exit_code"] = None
                self._state[task_id]["last_error"] = None
                return True, {"task": self.get_task(task_id)}, 200

            if process is None:
                return False, {"error": "Task is not running", "task": self._snapshot(task_id)}, 400

            self._stop_requested[task_id] = True
            self._append_log(task_id, "system", f"Stopping task {self.tasks[task_id]['label']}")

        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                capture_output=True,
                text=True,
            )
        else:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()

        return True, {"task": self.get_task(task_id)}, 200

    def get_logs(self, task_id: str, after: int = 0, limit: int = 200) -> dict | None:
        with self._lock:
            if task_id not in self.tasks:
                return None
            self._sync_buffer_from_file(task_id)

            limit = max(1, min(limit, 500))
            lines = [entry for entry in self._buffers[task_id] if entry["id"] > after]
            lines = lines[-limit:]
            cursor = self._cursors[task_id]

            return {
                "task_id": task_id,
                "cursor": cursor,
                "lines": lines,
                "log_path": str(self._log_path(task_id)),
            }
