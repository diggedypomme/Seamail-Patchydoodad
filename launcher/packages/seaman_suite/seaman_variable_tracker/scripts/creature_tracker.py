import os
import sys
import time
import json
import socketio
import ctypes
from pathlib import Path

_SUITE = Path(__file__).resolve().parents[2]
if str(_SUITE) not in sys.path:
    sys.path.insert(0, str(_SUITE))
from path_helpers import resolve_game_executable  # noqa: E402
import struct
import frida
from datetime import datetime

# Performance Config
POLL_INTERVAL = 0.8  # Default
EXE_NAME = resolve_game_executable().name
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "variables.json")

sio = socketio.Client()
TRACKER_DASHBOARD_URL = 'http://127.0.0.1:5081'
process_handle = None
instance_address = None
module_base = None

# Windows API Constants
PROCESS_VM_READ = 0x0010
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

def read_memory(handle, addr, size):
    if not handle or not addr: return None
    buffer = ctypes.create_string_buffer(size)
    bytes_read = ctypes.c_size_t()
    if kernel32.ReadProcessMemory(handle, addr, buffer, size, ctypes.byref(bytes_read)):
        return buffer.raw
    return None

def on_frida_message(message, data):
    global instance_address
    if message['type'] == 'send':
        payload = message['payload']
        if payload.get('type') == 'instance_found':
            instance_address = payload['address']
            print(f"[FOUND] Creature Instance at 0x{instance_address:x}")

def get_seaman_pid():
    device = frida.get_local_device()
    for p in device.enumerate_processes():
        if p.name == EXE_NAME:
            return p.pid
    return None

@sio.on('connect')
def on_connect():
    print("[SERVER] Connected to Flask-SocketIO")

@sio.on('update_frequency')
def on_freq_update(data):
    global POLL_INTERVAL
    POLL_INTERVAL = data.get('frequency', 0.8)
    print(f"[ENGINE] Frequency updated to {POLL_INTERVAL}s")

def run_engine():
    global instance_address, process_handle, module_base
    
    print(f"[ENGINE] Starting Hybrid Tracker for {EXE_NAME}...")
    
    # 1. Connect to dashboard server
    try:
        sio.connect(TRACKER_DASHBOARD_URL)
    except:
        print("[WARN] Could not connect to dashboard server. Running in headless mode.")

    # 2. Find Process
    pid = get_seaman_pid()
    while not pid:
        print(f"[WAIT] Waiting for {EXE_NAME}...")
        time.sleep(2)
        pid = get_seaman_pid()
    
    print(f"[OK] Found {EXE_NAME} (PID: {pid})")
    
    # 3. Phase 1: Frida Discovery
    session = frida.attach(pid)
    script_code = """
    var seaman_base = null;
    Process.enumerateModules().forEach(function(mod) {
        if (mod.name === '""" + EXE_NAME + """') { seaman_base = mod.base; }
    });
    if (seaman_base) {
        var hook_addr = seaman_base.add(0x7E60);
        Interceptor.attach(hook_addr, {
            onEnter: function(args) {
                send({ type: 'instance_found', address: this.context.ecx.toInt32() });
            }
        });
    }
    """
    script = session.create_script(script_code)
    script.on('message', on_frida_message)
    script.load()
    
    print("[DISCOVERY] Waiting for creature interaction (click in tank)...")
    while instance_address is None:
        time.sleep(0.5)
    
    # 4. Phase 2: Detach and RPM
    print("[DISCOVERY] Detaching Frida and switching to RPM Polling...")
    script.unload()
    session.detach()
    
    process_handle = kernel32.OpenProcess(PROCESS_VM_READ, False, pid)
    
    # Main Polling Loop
    print("[POLLING] Engine Active. Tracking 295+ variables.")
    
    with open(CONFIG_PATH, "r") as f:
        config_data = json.load(f)
        variables = config_data.get("high_value", [])

    while True:
        start_time = time.time()
        payload = {"timestamp": datetime.now().isoformat(), "variables": {}}
        
        for v in variables:
            try:
                # Calculate Address
                if v.get('root') == 'creature':
                    # Relative to instance
                    addr = (instance_address & 0xFFFFFFFF) + v['offsets'][0]
                else:
                    # Static global
                    addr = int(v['address'], 16)
                
                addr &= 0xFFFFFFFF  # Sanity mask
                
                # Read Value
                if v['type'] == 'float':
                    res = read_memory(process_handle, addr, 4)
                    val = struct.unpack('<f', res)[0] if res else "NULL"
                elif v['type'] == 'int' or v['type'] == 'hex':
                    res = read_memory(process_handle, addr, 4)
                    val = struct.unpack('<I', res)[0] if res else "NULL"
                    if v['type'] == 'hex' and isinstance(val, int):
                        val = f"0x{val:08x}"
                elif v['type'] == 'string':
                    # Read 32 chars
                    res = read_memory(process_handle, addr, 32)
                    val = res.split(b'\x00')[0].decode('ascii', 'ignore') if res else ""
                elif v['type'] == 'magic':
                    res = read_memory(process_handle, addr, 4)
                    val = res[::-1].decode('ascii', 'ignore') if res else ""
                else:
                    res = read_memory(process_handle, addr, 4)
                    val = struct.unpack('<I', res)[0] if res else 0
                
                payload["variables"][v['name']] = val
            except Exception as e:
                payload["variables"][v['name']] = "ERR"
        
        # Emit to dashboard — reconnect if dashboard came up after engine started
        if not sio.connected:
            try:
                sio.connect(TRACKER_DASHBOARD_URL)
            except Exception:
                pass
        if sio.connected:
            sio.emit('variable_update', payload)
        
        # Performance control
        elapsed = time.time() - start_time
        sleep_time = max(0.01, POLL_INTERVAL - elapsed)
        time.sleep(sleep_time)

if __name__ == "__main__":
    run_engine()
