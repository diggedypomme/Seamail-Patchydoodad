import frida
import sys
import os
from datetime import datetime
from pathlib import Path

_SUITE = Path(__file__).resolve().parents[1]
if str(_SUITE) not in sys.path:
    sys.path.insert(0, str(_SUITE))
from path_helpers import resolve_game_executable  # noqa: E402

TARGET_EXE = resolve_game_executable().name


def on_message(message, data):
    log_file = os.path.join(os.path.dirname(__file__), "interaction_log.txt")
    text = ""
    if message['type'] == 'send':
        text = str(message['payload'])
    elif message['type'] == 'log':
        text = str(message['payload'])
    elif message['type'] == 'error':
        text = f"[*] ERROR: {message['stack']}"

    if text:
        print(text)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def main():
    script_path = os.path.join(os.path.dirname(__file__), "fix_interaction_v33.js")
    log_file = os.path.join(os.path.dirname(__file__), "interaction_log.txt")

    try:
        session = frida.attach(TARGET_EXE)

        with open(script_path, "r", encoding="utf-8") as f:
            js_code = f.read()

        script = session.create_script(js_code)
        script.on('message', on_message)
        script.load()

        start_msg = f"[*] PURE FIX (NO EVENT BLOCKING) v33 LOADED. Logging to {log_file}."
        print(start_msg)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n--- SESSION START (V33 - PURE FIX): {datetime.now()} ---\n")
            f.write(start_msg + "\n")

        print("\n--- RPC Commands ---")
        print("  vocab          - Show words Seaman is listening for")
        print("  pick <number>  - Pick a word from the vocab list to send")
        print("  spoof <word>   - Manually send a specific word")
        print("  status         - Check engine state")
        print("  discover       - Re-discover the engine pointer")
        print("  Press Ctrl+C to exit\n")

        last_vocab = []

        while True:
            try:
                cmd = input("> ").strip()
                if cmd.startswith("spoof "):
                    word = cmd[6:]
                    result = script.exports_sync.spoof_word(word)
                    print(f"  -> {result}")
                elif cmd == "vocab":
                    v = script.exports_sync.get_vocab()
                    print(f"  Label: {v['label']}")
                    print(f"  Collecting: {v['collecting']}")
                    last_vocab = v['words']
                    if last_vocab:
                        print(f"  --- Vocabulary ({len(last_vocab)} words) ---")
                        for i, w in enumerate(last_vocab):
                            print(f"    [{i}] {w}")
                    else:
                        print("  (no words collected yet)")
                elif cmd.startswith("pick "):
                    try:
                        idx = int(cmd[5:])
                        if not last_vocab:
                            v = script.exports_sync.get_vocab()
                            last_vocab = v['words']
                        if 0 <= idx < len(last_vocab):
                            word = last_vocab[idx]
                            print(f"  Sending: {word}")
                            result = script.exports_sync.spoof_word(word)
                            print(f"  -> {result}")
                        else:
                            print(f"  Invalid index. Use 0-{len(last_vocab)-1}")
                    except ValueError:
                        print("  Usage: pick <number>")
                elif cmd == "status":
                    status = script.exports_sync.get_status()
                    print(f"  Engine: {status['enginePtr']}")
                    print(f"  SpeechMgr: {status['speechMgr']}")
                    print(f"  CreatureID: {status['creatureId']}")
                    print(f"  Label: {status['currentLabel']}")
                    print(f"  VocabCount: {status['vocabCount']}")
                    print(f"  GrowGetForced: {status['growGetForced']}")
                elif cmd == "discover":
                    result = script.exports_sync.discover_engine()
                    print(f"  -> {'Found' if result else 'Not found'}")
                elif cmd:
                    print("  Commands: vocab, pick <n>, spoof <word>, status, discover")
            except EOFError:
                break

    except frida.ProcessNotFoundError:
        print(f"[!] Could not find {TARGET_EXE}. Is the game running?")
    except KeyboardInterrupt:
        print("\n[*] Detaching...")
    except Exception as e:
        print(f"[!] Error: {e}")


if __name__ == "__main__":
    main()
