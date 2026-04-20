"""
Force Persistent Office Monitor - DEBUG VERSION (Safe Hooks)
-----------------------------------------------------------
1. Restore Safe V8 Hooks first.
2. If this works, we will re-inject the bypass.
"""
import frida
import sys

JS_SCRIPT = """
console.log("[*] Debugging Persistent Monitor...");

const speechDll = Process.findModuleByName("SpeechEngine.dll");
const seamanExe = Process.enumerateModules()[0];
const msvcrt = Process.findModuleByName("msvcrt.dll");
const advapi32 = Process.findModuleByName("advapi32.dll");
const user32 = Process.findModuleByName("user32.dll");

if (speechDll && msvcrt) {
    const base = speechDll.base;
    const size = speechDll.size;
    const stricmp = msvcrt.getExportByName("_stricmp");

    Interceptor.attach(stricmp, {
        onEnter: function(args) {
            const relAddr = this.returnAddress.sub(base);
            if (relAddr.compare(0) >= 0 && relAddr.compare(size) < 0) {
                const target = args[0].readAnsiString();
                const current = args[1].readAnsiString();
                
                // Logging ONLY (V8 style)
                if (relAddr.equals(0x35f2)) { // Loader
                    if (target.toLowerCase() !== current.toLowerCase()) {
                        send({type: 'loader', name: target});
                    }
                } 
                else if (relAddr.equals(0x4766)) { // Label
                    if (target.toLowerCase() === current.toLowerCase()) {
                        send({type: 'label', name: target});
                    }
                }
            }
        }
    });
}

// Minimal Spoofing
if (user32) {
    const findWindow = user32.getExportByName("FindWindowExA");
    const fakeHwnd = ptr(0xDEADBEEF);
    Interceptor.attach(findWindow, {
        onEnter: function(args) {
            let cls = args[2].isNull() ? "" : args[2].readAnsiString();
            if (cls.includes("Msoassistant") || cls.includes("Agentanim")) this.spoof = true;
        },
        onLeave: function(retval) {
            if (this.spoof) retval.replace(fakeHwnd);
        }
    });
}

console.log("[+] Debug Monitor Ready.");
"""

class DebugMonitor:
    def on_message(self, message, data):
        if message['type'] == 'send':
            payload = message['payload']
            print(f"[*] {payload['type'].upper()} -> {payload['name']}")

def main():
    device = frida.get_local_device()
    pid = next((proc.pid for proc in device.enumerate_processes() if 'seaman' in proc.name.lower()), None)
    if not pid: return

    monitor = DebugMonitor()
    session = frida.attach(pid)
    script = session.create_script(JS_SCRIPT)
    script.on('message', monitor.on_message)
    script.load()
    sys.stdin.read()

if __name__ == '__main__':
    main()
