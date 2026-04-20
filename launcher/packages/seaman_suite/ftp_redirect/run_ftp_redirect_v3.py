"""
run_ftp_redirect_v3.py
Attach-mode. Attaches to the already-running game.

Usage:
  1. Start dual_http_ftp_server (admin, port 21).
  2. Start the game normally.
  3. Run this script — it attaches and installs the hook.
  4. Trigger whatever causes the FTP call in-game.
  Ctrl+C to detach.
"""

import frida
import json
import os
import sys
from datetime import datetime
from pathlib import Path

_SUITE = Path(__file__).resolve().parents[1]
if str(_SUITE) not in sys.path:
    sys.path.insert(0, str(_SUITE))
from path_helpers import resolve_game_executable  # noqa: E402

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JS_FILE    = os.path.join(SCRIPT_DIR, 'ftp_redirect_v3.js')
LOG_FILE   = os.path.join(SCRIPT_DIR, 'ftp_redirect_log.txt')
TARGET_EXE = resolve_game_executable().name


def log(text: str) -> None:
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    line = f'[{ts}] {text}'
    print(line, flush=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def on_message(message, _data):
    if message['type'] == 'send':
        payload = message['payload']
        try:
            evt = json.loads(payload)
            if evt.get('event') == 'redirect':
                status = 'OK' if evt['success'] else 'FAILED (handle=NULL)'
                log(f"[REDIRECT] {evt['from']}:{evt['port']} -> {evt['to']}  [{status}]")
            else:
                log(str(payload))
        except (json.JSONDecodeError, TypeError):
            log(str(payload))
    elif message['type'] == 'error':
        log(f"[JS ERROR] {message['stack']}")


def main() -> int:
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f'\n--- SESSION START (ftp_redirect v3 / attach): {datetime.now()} ---\n')

    try:
        session = frida.attach(TARGET_EXE)
    except frida.ProcessNotFoundError:
        log(f'[!] {TARGET_EXE} not running. Start the game first.')
        return 1

    with open(JS_FILE, 'r', encoding='utf-8') as f:
        js_code = f.read()

    script = session.create_script(js_code)
    script.on('message', on_message)
    script.load()

    log(f'[*] Attached to {TARGET_EXE}.')
    log('[*] Now trigger the FTP action in-game (whatever caused the call before).')
    log('[*] You should see [REDIRECT] lines appear here when it fires.')
    log('[*] Ctrl+C to detach.\n')

    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass

    log('[*] Detaching...')
    try:
        session.detach()
    except Exception:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
