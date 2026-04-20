import frida
import sys
from pathlib import Path

_SUITE = Path(__file__).resolve().parents[1]
if str(_SUITE) not in sys.path:
    sys.path.insert(0, str(_SUITE))
from path_helpers import resolve_game_executable  # noqa: E402

PROCESS_NAME = resolve_game_executable().name
SCRIPT_FILE = "frida_menu_translate_v25.js"

def on_message(message, data):
    if message['type'] == 'send':
        print(f"[*] {message['payload']}")
    elif message['type'] == 'error':
        print(f"[!] {message['stack']}")

def main():
    try:
        session = frida.attach(PROCESS_NAME)
    except Exception as e:
        print(f"[!] {e}")
        return

    with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
        source = f.read()

    script = session.create_script(source)
    script.on('message', on_message)
    script.load()
    print(f"[*] V25 Loaded.")
    sys.stdin.read()

if __name__ == "__main__":
    main()
