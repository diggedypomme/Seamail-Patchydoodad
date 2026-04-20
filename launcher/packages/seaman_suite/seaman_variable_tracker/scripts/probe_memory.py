import ctypes
import struct
import frida
import time

def probe():
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    PROCESS_VM_READ = 0x0010
    
    # Find Seaman
    device = frida.get_local_device()
    processes = device.enumerate_processes()
    target = next((p for p in processes if "Seaman" in p.name), None)
    if not target:
        print("Seaman not found")
        return
    
    # Get Base
    session = frida.attach(target.pid)
    script = session.create_script("let b=null;Process.enumerateModules().forEach(m=>{if(m.name.toLowerCase().includes('seaman'))b=m.base;});send(b);")
    res = []
    script.on('message', lambda m, d: res.append(m['payload']) if m['type']=='send' else None)
    script.load()
    time.sleep(1)
    base = int(res[0], 16)
    print(f"Base: 0x{base:x}")
    
    handle = kernel32.OpenProcess(PROCESS_VM_READ, False, target.pid)
    addr = 0x004690a0
    
    dump_size = 0x600
    buffer = ctypes.create_string_buffer(dump_size)
    bytes_read = ctypes.c_size_t()
    if kernel32.ReadProcessMemory(handle, addr, buffer, dump_size, ctypes.byref(bytes_read)):
        print(f"--- Global Object Scan [0x{addr:x}] ---")
        # Check specific suspect offsets
        for offset in [0x0, 0x518, 0x53c, 0x540, 0x59c, 0x5a0]:
            if offset < dump_size:
                val = struct.unpack('<I', buffer[offset:offset+4])[0]
                print(f"Offset +0x{offset:03x}: 0x{val:08x} ({val})")
        
        print("\n--- Potential Heap Pointers / Floats ---")
        for i in range(0, dump_size, 4):
            val = struct.unpack('<I', buffer[i:i+4])[0]
            # Likely a pointer if in 0x0... or 0x1... range
            if 0x01000000 < val < 0x20000000:
                print(f"  +0x{i:03x}: 0x{val:08x} (Potential PTR)")
            
            # Likely a float
            f_val = struct.unpack('<f', buffer[i:i+4])[0]
            if 1.0 < abs(f_val) < 1000.0:
                 print(f"  +0x{i:03x}: {f_val:.4f} (Float)")

    else:
        print(f"Failed to read 0x{addr:x}")

    kernel32.CloseHandle(handle)
    session.detach()

if __name__ == "__main__":
    probe()
