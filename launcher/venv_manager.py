from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path
import json
import os
import subprocess
import sys


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class VenvManager:
    def __init__(self, tasks: dict[str, dict], venv_root: Path) -> None:
        self.tasks = tasks
        self.venv_root = venv_root
        self.venv_root.mkdir(parents=True, exist_ok=True)
        self.pip_cache_root = self.venv_root.parent / ".pip-cache"
        self.pip_cache_root.mkdir(parents=True, exist_ok=True)

    def _task_spec(self, task: dict) -> dict | None:
        key = task.get("venv_key")
        if not key:
            return None

        return {
            "key": key,
            "label": task.get("venv_label") or key,
            "requirements_path": task.get("venv_requirements"),
            "packages": task.get("venv_packages", []),
        }

    def _venv_dir(self, key: str) -> Path:
        return self.venv_root / key

    def _python_path(self, key: str) -> Path:
        return self._venv_dir(key) / "Scripts" / "python.exe"

    def _manifest_path(self, key: str) -> Path:
        return self._venv_dir(key) / ".launcher-venv.json"

    def _pip_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["PIP_CACHE_DIR"] = str(self.pip_cache_root)
        temp_root = self.venv_root.parent / ".tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        env["TMP"] = str(temp_root)
        env["TEMP"] = str(temp_root)
        return env

    def status_for_task(self, task: dict) -> dict:
        spec = self._task_spec(task)
        if spec is None:
            return {
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

        key = spec["key"]
        venv_dir = self._venv_dir(key)
        python_path = self._python_path(key)
        manifest_path = self._manifest_path(key)
        exists = python_path.exists()
        configured = manifest_path.exists() or exists

        source = None
        if manifest_path.exists():
            try:
                source = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                source = None
        elif exists:
            source = {
                "key": key,
                "label": spec["label"],
                "python_path": str(python_path),
                "manual": True,
            }

        return {
            "required": True,
            "ready": exists,
            "exists": exists,
            "configured": configured,
            "key": key,
            "label": spec["label"],
            "path": str(venv_dir),
            "python_path": str(python_path),
            "source": source,
        }

    def python_for_task(self, task: dict) -> Path | None:
        spec = self._task_spec(task)
        if spec is None:
            return None

        status = self.status_for_task(task)
        if not status["ready"]:
            return None
        return Path(status["python_path"])

    def create_for_task(self, task: dict) -> tuple[bool, dict, int]:
        spec = self._task_spec(task)
        if spec is None:
            return False, {
                "error": "This task does not define a dedicated virtual environment.",
                "log_lines": [],
            }, 400

        key = spec["key"]
        venv_dir = self._venv_dir(key)
        python_path = self._python_path(key)
        manifest_path = self._manifest_path(key)
        log_lines: list[dict[str, str]] = []
        requirements_path = None
        if spec["requirements_path"]:
            requirements_path = Path(spec["requirements_path"])
            if not requirements_path.is_absolute():
                requirements_path = Path(__file__).resolve().parent.parent / spec["requirements_path"]

        def record(stream: str, text: str) -> None:
            clean = text.strip()
            if clean:
                log_lines.append({"stream": stream, "text": clean})

        def run_step(command: list[str], label: str) -> None:
            record("system", label)
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                env=self._pip_env(),
            )
            if completed.stdout:
                for line in completed.stdout.splitlines():
                    record("stdout", line)
            if completed.stderr:
                for line in completed.stderr.splitlines():
                    record("stderr", line)

        try:
            if not python_path.exists():
                run_step(
                    [sys.executable, "-m", "venv", str(venv_dir)],
                    f"Creating virtual environment at {venv_dir}",
                )
            else:
                record("system", f"Using existing virtual environment at {venv_dir}")

            install_steps: list[str] = []

            run_step(
                [str(python_path), "-m", "pip", "install", "--upgrade", "pip"],
                f"Upgrading pip in {spec['label']}",
            )
            install_steps.append("pip")

            if requirements_path is not None:
                run_step(
                    [str(python_path), "-m", "pip", "install", "-r", str(requirements_path)],
                    f"Installing requirements from {requirements_path.name}",
                )
                install_steps.append(f"requirements:{requirements_path.name}")

            packages = spec["packages"] or []
            if packages:
                run_step(
                    [str(python_path), "-m", "pip", "install", *packages],
                    f"Installing packages: {', '.join(packages)}",
                )
                install_steps.append("packages")

            manifest = {
                "created_at": utc_now(),
                "key": key,
                "label": spec["label"],
                "python_path": str(python_path),
                "requirements_path": str(requirements_path) if requirements_path else None,
                "packages": packages,
                "steps": install_steps,
            }
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            record("system", f"{spec['label']} environment is ready.")
            return True, {"venv": self.status_for_task(task), "log_lines": log_lines}, 200
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            if stdout:
                for line in stdout.splitlines():
                    record("stdout", line)
            if stderr:
                for line in stderr.splitlines():
                    record("stderr", line)
            message = stderr or stdout or str(exc)
            record("system", f"Environment setup failed: {message}")
            return False, {"error": message, "venv": self.status_for_task(task), "log_lines": log_lines}, 500
