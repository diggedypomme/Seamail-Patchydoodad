import frida
import sys
import time
import os
import threading

JS_HOOK = """
Interceptor.attach(Module.findExportByName("kernel32.dll", "DeleteFileA"), {
    onEnter: function (args) {
        var filename = Memory.readCString(args[0]);
        if (filename && filename.indexOf("WeatherIndex.dat") !== -1) {
            send("[WEATHER DAEMON] Prevented engine from deleting WeatherIndex.dat!");
            args[0] = NULL; 
        }
    }
});

var weatherGetCalled = false;
Interceptor.attach(Module.findExportByName("kernel32.dll", "LoadLibraryA"), {
    onEnter: function (args) {
        this.libName = Memory.readCString(args[0]);
    },
    onLeave: function (retval) {
        if (this.libName && this.libName.indexOf("WeatherGet.dll") !== -1 && !weatherGetCalled) {
            weatherGetCalled = true;
            send("[WEATHER DAEMON] WeatherGet.dll Loaded. Neutralizing WeatherGetOpen...");
            
            var weatherGetOpenAddr = Module.findExportByName(this.libName, "WeatherGetOpen");
            if (weatherGetOpenAddr) {
                Interceptor.replace(weatherGetOpenAddr, new NativeCallback(function (param) {
                    send("[WEATHER DAEMON] Network bypass successful! Engine is reading local dat.");
                    return 1; 
                }, 'int', ['int']));
            }
        }
    }
});
"""

def generate_dummy_weather(target_dir):
    out_path = os.path.join(target_dir, "WeatherIndex.dat")
    days = []
    
    # Day 1: 85% Rain, Min 12, Max 28
    days.append([1, 0, 0, 85, 12, 28])
    for _ in range(6):
        days.append([0, 0, 0, 0, 0, 0])
        
    with open(out_path, "w") as f:
        for day in days:
            for val in day:
                f.write(f"{val}\n")
    print(f"[*] Weather daemon refreshed WeatherIndex.dat at {out_path}")

def on_message(message, data):
    if message["type"] == "send":
        print(f"[*] {message['payload']}")

def main():
    target_exe = "Seaman_Adult_v2.exe"  # Defaulting to the custom patched executable
    print(f"[*] Weather Bypass Daemon starting...")
    print(f"[*] Waiting for {target_exe} to launch...")
    
    # SeaMail/ is four levels up from this file (weather_bypass_daemon/ -> packages/ -> launcher/ -> repo_root/)
    _repo_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    target_dir = os.path.join(_repo_root, "SeaMail")
    generate_dummy_weather(target_dir)

    session = None
    while session is None:
        try:
            session = frida.attach(target_exe)
        except frida.ProcessNotFoundError:
            time.sleep(1)
            
    print(f"[*] Attached to {target_exe}! Injecting weather network neutralization...")
    script = session.create_script(JS_HOOK)
    script.on("message", on_message)
    script.load()
    
    print("[*] Weather daemon is active. Leave this running to protect the weather index.")
    
    try:
        sys.stdin.read()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
