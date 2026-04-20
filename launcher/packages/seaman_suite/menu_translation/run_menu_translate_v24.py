import frida
import sys

PROCESS_NAME = "Seaman_1_2_57.exe"
SCRIPT_FILE = "frida_menu_translate_v24.js"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
    print(f"[*] V24 Loaded.")
    sys.stdin.read()

if __name__ == "__main__":
    main()
