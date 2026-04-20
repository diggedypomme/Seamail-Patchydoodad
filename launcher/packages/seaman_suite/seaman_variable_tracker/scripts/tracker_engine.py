import frida
import json
import time
import socketio
import os
import ctypes
import struct
from datetime import datetime

# Configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "variables.json")
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")

# Windows API
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
PROCESS_VM_READ = 0x0010
OpenProcess = kernel32.OpenProcess
ReadProcessMemory = kernel32.ReadProcessMemory
CloseHandle = kernel32.CloseHandle

# SocketIO Client
sio = socketio.Client()
polling_frequency = 0.8  # Slow down a bit for 286 vars
TRACKER_DASHBOARD_URL = 'http://127.0.0.1:5081'

# Global State
base_address = None
process_handle = None

def get_base_address():
    try:
        device = frida.get_local_device()
        processes = device.enumerate_processes()
        target = next((p for p in processes if "Seaman" in p.name), None)
        if not target: return None, None
        session = frida.attach(target.pid)
        script = session.create_script("let b=null;Process.enumerateModules().forEach(m=>{if(m.name.toLowerCase().includes('seaman'))b=m.base;});send(b);")
        res = []
        script.on('message', lambda m, d: res.append(m['payload']) if m['type']=='send' else None)
        script.load()
        start = time.time()
        while not res and (time.time()-start < 3): time.sleep(0.1)
        session.detach()
        return int(res[0], 16), target.pid if res else None
    except: return None, None

def read_memory(handle, address, size):
    if address < 0x10000: return None # Safety
    buffer = ctypes.create_string_buffer(size)
    bytes_read = ctypes.c_size_t()
    if ReadProcessMemory(handle, address, buffer, size, ctypes.byref(bytes_read)):
        return buffer.raw
    return None

def is_likely_float(val_int):
    """Simple heuristic for IEEE 754 float detection."""
    try:
        f = struct.unpack('>f', struct.pack('>I', val_int & 0xFFFFFFFF))[0]
        return abs(f) > 0.00001 and abs(f) < 100000000.0
    except: return False

def start_engine():
    global polling_frequency, base_address, process_handle
    print("[Engine] --- GEM Var Tracker 2.0 (MASSIVE MODE) ---")
    
    base_address, pid = get_base_address()
    if not base_address:
        print("[Engine] ❌ Error Finding Process")
        return
    process_handle = OpenProcess(PROCESS_VM_READ, False, pid)
    
    try:
        sio.connect(TRACKER_DASHBOARD_URL)
        print("[Engine] ✅ Connected to Flask!")
    except: pass

    with open(CONFIG_PATH, "r") as f:
        variables = json.load(f).get("high_value", [])

    log_file = os.path.join(LOG_DIR, f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    print(f"[Engine] Tracking {len(variables)} variables. Polling {1/polling_frequency:.1f} Hz")

    try:
        while True:
            payload = {"timestamp": datetime.now().isoformat(), "variables": {}}
            for v in variables:
                try:
                    addr = int(v['address'], 16)
                    target_addr = addr
                    
                    # Pointer Resolution
                    if v.get('is_pointer', False):
                        raw = read_memory(process_handle, addr, 4)
                        if raw:
                            target_addr = struct.unpack('<I', raw)[0]
                        else: target_addr = 0
                    
                    if target_addr != 0:
                        # Apply Offsets
                        for i, off in enumerate(v.get('offsets', [])):
                            if i < len(v['offsets']) - 1:
                                raw = read_memory(process_handle, target_addr + off, 4)
                                if raw: target_addr = struct.unpack('<I', raw)[0]
                                else: target_addr = 0; break
                            else: target_addr += off
                        
                        if target_addr != 0:
                            res_raw = read_memory(process_handle, target_addr, 4)
                            if res_raw:
                                val_int = struct.unpack('<I', res_raw)[0]
                                
                                # Type Smart Detection
                                if v['type'] == 'float' or (v['type'] == 'pointer' and is_likely_float(val_int)):
                                    val = struct.unpack('<f', res_raw)[0]
                                elif v['type'] == 'string':
                                    str_raw = read_memory(process_handle, target_addr, 64)
                                    if str_raw:
                                        # Try ASCII first
                                        null_pos = str_raw.find(b'\x00')
                                        if null_pos != -1:
                                            val = str_raw[:null_pos].decode('ascii', errors='ignore')
                                        else:
                                            # Try UTF-16 (sometimes used in games)
                                            val = str_raw.decode('utf-16', errors='ignore').split('\0')[0]
                                    else: val = "ERR"
                                elif v['type'] == 'magic':
                                    # 4-byte ASCII magic like 'face'
                                    try:
                                        val = f"'{res_raw.decode('ascii', errors='ignore')}' (0x{val_int:08x})"
                                    except: val = f"0x{val_int:08x}"
                                elif v['type'] == 'pointer':
                                    val = f"0x{val_int:08x}"
                                else: # int
                                    val = struct.unpack('<i', res_raw)[0]
                                
                                payload["variables"][v['name']] = val
                    else:
                        payload["variables"][v['name']] = "NULL"
                except:
                    payload["variables"][v['name']] = "ERR"

            if sio.connected:
                sio.emit('variable_update', payload)
            
            # Print first 5 for sanity
            sample = list(payload["variables"].items())[:5]
            print(f"Sample data: {sample}")
            
            time.sleep(polling_frequency)
            
    except KeyboardInterrupt: print("[Engine] Stopping...")
    finally:
        if process_handle: CloseHandle(process_handle)

if __name__ == "__main__":
    start_engine()
