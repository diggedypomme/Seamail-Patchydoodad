from pathlib import Path
import sys

from flask import Flask, jsonify, render_template, request

from task_manager import TaskManager
from task_registry import PROJECT_ROOT, group_tasks, task_map
from todo_store import TodoStore
from venv_manager import VenvManager

SUITE_ROOT = PROJECT_ROOT / "launcher" / "packages" / "seaman_suite"
if str(SUITE_ROOT) not in sys.path:
    sys.path.insert(0, str(SUITE_ROOT))

MAIL_SERVER_ROOT = PROJECT_ROOT / "launcher" / "packages" / "seaman_suite" / "smtp_and_pop_server"
if str(MAIL_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(MAIL_SERVER_ROOT))

from mailbox_store import MailboxStore  # noqa: E402
from path_helpers import load_launcher_config, save_launcher_config, validate_paths  # noqa: E402


app = Flask(__name__, template_folder="templates", static_folder="static")
tasks = task_map()
venvs = VenvManager(tasks, PROJECT_ROOT / "launcher" / "venvs")
manager = TaskManager(tasks, PROJECT_ROOT / "launcher" / "logs", venv_manager=venvs)
mailbox = MailboxStore(MAIL_SERVER_ROOT)
todo_store = TodoStore(PROJECT_ROOT / "launcher" / "todo_data.json")


@app.get("/")
def index():
    grouped = {}
    for group_name, raw_tasks in group_tasks().items():
        result = []
        for task in raw_tasks:
            if task.get("runner") == "separator":
                result.append(task)
            else:
                t = manager.get_task(task["id"])
                if t is not None:
                    result.append(t)
        grouped[group_name] = result
    return render_template("index.html", grouped_tasks=grouped)


@app.get("/api/tasks")
def list_tasks():
    group = request.args.get("group")
    return jsonify({"tasks": manager.list_tasks(group=group)})


@app.get("/api/tasks/<task_id>")
def get_task(task_id: str):
    task = manager.get_task(task_id)
    if task is None:
        return jsonify({"error": "Unknown task"}), 404
    return jsonify(task)


@app.post("/api/tasks/<task_id>/start")
def start_task(task_id: str):
    success, payload, status_code = manager.start_task(task_id)
    return jsonify(payload), status_code


@app.post("/api/tasks/<task_id>/venv/create")
def create_task_venv(task_id: str):
    success, payload, status_code = manager.create_task_venv(task_id)
    return jsonify(payload), status_code


@app.post("/api/tasks/<task_id>/stop")
def stop_task(task_id: str):
    success, payload, status_code = manager.stop_task(task_id)
    return jsonify(payload), status_code


@app.get("/api/tasks/<task_id>/logs")
def get_logs(task_id: str):
    after = request.args.get("after", default=0, type=int)
    limit = request.args.get("limit", default=200, type=int)
    payload = manager.get_logs(task_id, after=after, limit=limit)
    if payload is None:
        return jsonify({"error": "Unknown task"}), 404
    return jsonify(payload)


@app.get("/api/mail/status")
def mail_status():
    standard = manager.get_task("smtp_pop_server")
    debug = manager.get_task("smtp_pop_server_debug")
    return jsonify({"standard": standard, "debug": debug})


@app.get("/api/mail/inbox")
def mail_inbox():
    return jsonify(mailbox.list_inbox_messages())


@app.post("/api/mail/inbox")
def create_mail_message():
    payload = request.get_json(silent=True) or {}
    try:
        message = mailbox.create_message(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"message": message}), 201


@app.post("/api/mail/inbox/<message_id>/enable")
def set_mail_enabled(message_id: str):
    payload = request.get_json(silent=True) or {}
    enabled = bool(payload.get("enabled"))
    reset_pulled = bool(payload.get("reset_pulled"))
    message = mailbox.set_message_enabled(message_id, enabled, reset_pulled=reset_pulled)
    if message is None:
        return jsonify({"error": "Unknown message"}), 404
    return jsonify({"message": message})


@app.get("/api/mail/outbox")
def mail_outbox():
    return jsonify({"messages": mailbox.list_outbox_messages()})


@app.get("/api/todo")
def get_todo():
    return jsonify(todo_store.list_categories())


@app.post("/api/todo/<category_id>/<item_id>")
def update_todo(category_id: str, item_id: str):
    payload = request.get_json(silent=True) or {}
    if "progress" not in payload:
        return jsonify({"error": "Missing progress"}), 400
    try:
        item = todo_store.update_item(category_id, item_id, payload["progress"])
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    if item is None:
        return jsonify({"error": "Unknown to-do item"}), 404
    return jsonify(todo_store.list_categories())


@app.get("/api/config")
def get_config():
    config = load_launcher_config()
    validation = validate_paths(
        game_root=config.get("game_root"),
        seamail_root=config.get("seamail_root"),
        game_executable=config.get("game_executable"),
    )
    return jsonify({"config": config, "validation": validation})


@app.post("/api/config")
def save_config():
    payload = request.get_json(silent=True) or {}
    config = save_launcher_config(payload)
    validation = validate_paths(
        game_root=config.get("game_root"),
        seamail_root=config.get("seamail_root"),
        game_executable=config.get("game_executable"),
    )
    return jsonify({"config": config, "validation": validation})


@app.post("/api/config/test")
def test_config():
    payload = request.get_json(silent=True) or {}
    validation = validate_paths(
        game_root=payload.get("game_root"),
        seamail_root=payload.get("seamail_root"),
        game_executable=payload.get("game_executable"),
    )
    return jsonify({"validation": validation})


@app.post("/api/config/choose-folder")
def choose_folder():
    payload = request.get_json(silent=True) or {}
    target = payload.get("target", "seamail_root")
    initial_dir = payload.get("initial_dir")

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(initialdir=initial_dir or str(PROJECT_ROOT))
        root.destroy()
    except Exception as exc:  # pragma: no cover - desktop integration fallback
        return jsonify({"error": str(exc)}), 500

    if not selected:
        return jsonify({"cancelled": True})

    return jsonify({"target": target, "path": selected})


@app.post("/api/config/choose-file")
def choose_file():
    payload = request.get_json(silent=True) or {}
    target = payload.get("target", "game_executable")
    initial_dir = payload.get("initial_dir")

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askopenfilename(
            initialdir=initial_dir or str(PROJECT_ROOT),
            filetypes=[("Windows executables", "*.exe"), ("All files", "*.*")],
        )
        root.destroy()
    except Exception as exc:  # pragma: no cover - desktop integration fallback
        return jsonify({"error": str(exc)}), 500

    if not selected:
        return jsonify({"cancelled": True})

    return jsonify({"target": target, "path": selected})


DB_MANAGER_ROOT = PROJECT_ROOT / "launcher" / "packages" / "seaman_suite" / "db_manager_main"
if str(DB_MANAGER_ROOT) not in sys.path:
    sys.path.insert(0, str(DB_MANAGER_ROOT))

# Key variables to show in the creature snapshot
SNAPSHOT_KEYS = [
    ("SeamanPC\\Bio\\Grow",                  "Stage"),
    ("SeamanPC\\Bio\\OldGrow",               "Prev Stage"),
    ("SeamanPC\\Bio\\Hunger",                "Hunger"),
    ("SeamanPC\\Bio\\Mood",                  "Mood"),
    ("SeamanPC\\Bio\\Light",                 "Light"),
    ("SeamanPC\\Bio\\DNA\\Mine\\Element01",  "DNA 1"),
    ("SeamanPC\\Bio\\DNA\\Mine\\Element02",  "DNA 2"),
    ("SeamanPC\\Bio\\PlayTime\\DayTimes",    "Play today"),
    ("SeamanPC\\Bio\\PlayTime\\Total",       "Total play"),
    ("User\\Name",                           "User"),
    ("User\\Age",                            "Age"),
    ("User\\Sex",                            "Sex"),
]


@app.get("/api/snapshot")
def creature_snapshot():
    try:
        from db_parser import parse_udb
        config = load_launcher_config()
        seamail_root = Path(config.get("seamail_root", ""))
        udb_path = seamail_root / "hostDB" / "Seaman.udb"
        if not udb_path.exists():
            return jsonify({"error": f"Seaman.udb not found at {udb_path}"})

        records = parse_udb(str(udb_path))
        # Records are {"path": str, "elements": [{"value": str, ...}]}
        lookup = {}
        for r in records:
            if "path" in r and r.get("elements"):
                lookup[r["path"]] = r["elements"][0]["value"]

        snapshot = []
        for path, label in SNAPSHOT_KEYS:
            val = lookup.get(path)
            if val is not None:
                snapshot.append({"label": label, "value": val, "path": path})

        return jsonify({"snapshot": snapshot})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.get("/api/envs")
def env_status():
    env_keys = ["launcher-app", "launcher-frida"]
    result = {}
    for key in env_keys:
        python_path = PROJECT_ROOT / "launcher" / "venvs" / key / "Scripts" / "python.exe"
        result[key] = {"ready": python_path.exists()}
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
