from flask import Flask, render_template, jsonify, request
import os
import json
from core.patch_engine import PatchEngine

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# CONFIGURATION
# seaman_patcher lives alongside launcher/ and SeaMail/ inside the same repo root.
# SeaMail folder is read from launcher/config.json (one level up).
# Override with SEAMAN_WORKSPACE env var if needed.
_REPO_ROOT       = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_LAUNCHER_CONFIG = os.path.join(_REPO_ROOT, "launcher", "config.json")

def _load_workspace_dir():
    env_override = os.environ.get("SEAMAN_WORKSPACE", "").strip()
    if env_override and os.path.isdir(env_override):
        return env_override
    try:
        with open(_LAUNCHER_CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
        root = cfg.get("seamail_root", "").strip()
        if root and os.path.isdir(root):
            return root
        print(f"WARNING: seamail_root in config not found: {root!r}")
    except FileNotFoundError:
        print(f"WARNING: launcher config not found at {_LAUNCHER_CONFIG}")
    except Exception as e:
        print(f"WARNING: could not read launcher config: {e}")
    # Fall back to SeaMail/ next to this file (same repo root)
    fallback = os.path.join(_REPO_ROOT, "SeaMail")
    if os.path.isdir(fallback):
        return fallback
    print("Set SEAMAN_WORKSPACE env var or configure seamail_root in launcher/config.json")
    return None

WORKSPACE_DIR = _load_workspace_dir()
if not WORKSPACE_DIR:
    import sys; sys.exit(1)
MASTER_DIR    = os.path.join(_REPO_ROOT, "SeaMail_original")
PATCH_DIR     = os.path.join(os.path.dirname(__file__), "patches")

os.makedirs(PATCH_DIR, exist_ok=True)

engine = PatchEngine(
    default_target_file=os.path.join(WORKSPACE_DIR, "Seaman.exe"),
    workspace_dir=WORKSPACE_DIR,
)


def load_all_patches():
    patch_list = []
    for filename in sorted(os.listdir(PATCH_DIR)):
        if not filename.endswith('.json'):
            continue
        path = os.path.join(PATCH_DIR, filename)
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            data['filename'] = filename
            data['status'] = engine.check_patch_status(data)
            patch_list.append(data)
        except Exception as e:
            patch_list.append({'filename': filename, 'name': filename, 'status': f'Error: {e}'})
    return patch_list


@app.route('/')
def index():
    return render_template('index.html', workspace=WORKSPACE_DIR)


@app.route('/api/patches')
def get_patches():
    return jsonify(load_all_patches())


@app.route('/api/apply', methods=['POST'])
def apply_patch():
    filename = request.json.get('filename')
    path = os.path.join(PATCH_DIR, filename)
    with open(path, 'r') as f:
        data = json.load(f)
    success, message = engine.apply_patch(data)
    return jsonify({"success": success, "message": message})


@app.route('/api/revert', methods=['POST'])
def revert_patch():
    filename = request.json.get('filename')
    path = os.path.join(PATCH_DIR, filename)
    with open(path, 'r') as f:
        data = json.load(f)
    success, message = engine.revert_patch(data)
    return jsonify({"success": success, "message": message})


@app.route('/api/apply_all', methods=['POST'])
def apply_all():
    results = []
    for patch in load_all_patches():
        if patch['status'] == 'Installed':
            results.append({'filename': patch['filename'], 'success': True, 'message': 'Already installed'})
            continue
        path = os.path.join(PATCH_DIR, patch['filename'])
        with open(path, 'r') as f:
            data = json.load(f)
        success, message = engine.apply_patch(data)
        results.append({'filename': patch['filename'], 'success': success, 'message': message})
    return jsonify(results)


@app.route('/api/revert_all', methods=['POST'])
def revert_all():
    results = []
    for patch in load_all_patches():
        if patch['status'] == 'Missing':
            results.append({'filename': patch['filename'], 'success': True, 'message': 'Already original'})
            continue
        path = os.path.join(PATCH_DIR, patch['filename'])
        with open(path, 'r') as f:
            data = json.load(f)
        success, message = engine.revert_patch(data)
        results.append({'filename': patch['filename'], 'success': success, 'message': message})
    return jsonify(results)


if __name__ == '__main__':
    app.run(debug=True, port=5005)
