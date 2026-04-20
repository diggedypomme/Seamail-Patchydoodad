# Local Launcher Scaffold

This folder contains a local-only Flask launcher for the Seaman / Seamail toolchain.

## Environment Model

The launcher now uses two shared virtual environments:

- `launcher-app`
  - The non-Frida environment for the launcher itself plus the Flask, Socket.IO, DB, weather, mail, and FTP tools.
- `launcher-frida`
  - Everything in `launcher-app`, plus the Frida, translation, image, and client Socket.IO packages used by hook and overlay tools.

Requirements live in:

- `requirements.app.txt`
- `requirements.frida.txt`

## Layout

- `app.py`
  - Flask entrypoint serving the UI and local API routes.
- `task_registry.py`
  - Central list of launcher-managed tasks.
  - Existing scripts can stay in `debug_components/...` and be referenced here.
- `task_manager.py`
  - Starts and stops child Python processes, captures logs, and reports task state.
- `templates/index.html`
  - Version A-inspired launcher page.
- `static/css/launcher.css`
  - Launcher styling.
- `static/js/launcher.js`
  - Tab behavior, task actions, and active-log polling.
- `logs/`
  - Per-task log files written by the launcher.
- `log_dump/`
  - Previous-session task logs. On each launcher boot, existing logs are moved here so the new session starts fresh.
- `packages/`
  - Intact imported tool bundles that have their own templates, static assets, or data folders.
- `scripts/`
  - Recommended home for new launcher-specific scripts.

## Where Sub Scripts Should Go

You have two good options:

1. Keep existing reverse-engineering scripts where they already live.
   - Example: `debug_components/toubletap_menu/direct_menu.py`
   - Register them in `task_registry.py`.

2. Keep larger imported mini-projects intact under `launcher/packages/`.
   - Current imported bundle: `launcher/packages/seaman_suite/`
   - This is the right home for things like DB tools, tracker dashboards, servers, and overlays that already have their own folder structure.

3. Put new launcher-oriented wrapper scripts in `launcher/scripts/`.
   - Example folders already suggested:
     - `launcher/scripts/translation/`
     - `launcher/scripts/conversion/`
     - `launcher/scripts/streaming/`
     - `launcher/scripts/admin/`

That split works well because it lets the launcher own its stable entrypoints without forcing you to flatten or break the imported tool bundles.

## Running It

Set up the launcher env with:

```bat
launcher\setup_launcher_app_env.bat
```

Set up the shared Frida env with:

```bat
launcher\setup_launcher_frida_env.bat
```

Then start the launcher with:

```bat
launcher\run_launcher.bat
```

Then open:

```text
http://127.0.0.1:5000
```
