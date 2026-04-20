/*
 * ftp_redirect_v3.js
 * Attach-mode. Hooks InternetConnectA via Process.findModuleByName
 * (compatible with older Frida builds).
 * Watches LoadLibrary in case wininet.dll isn't loaded yet.
 */

const FROM_HOST = 'www.seamail.tv';
const TO_HOST   = '127.0.0.1';

// Allocate redirect string manually — avoids Memory.allocAnsiString
// compat issues across Frida versions.
const redirectBuf = Memory.alloc(32);
(function() {
    const bytes = [];
    for (let i = 0; i < TO_HOST.length; i++) bytes.push(TO_HOST.charCodeAt(i));
    bytes.push(0);
    redirectBuf.writeByteArray(bytes);
})();

let hooked = false;

function installHook() {
    if (hooked) return true;

    const mod = Process.findModuleByName('wininet.dll');
    if (!mod) return false;

    let fnAddr = null;
    try {
        fnAddr = mod.findExportByName('InternetConnectA');
    } catch (_) {}

    if (!fnAddr) {
        // Fallback: scan exports manually
        mod.enumerateExports().forEach(exp => {
            if (exp.name === 'InternetConnectA') fnAddr = exp.address;
        });
    }

    if (!fnAddr) {
        send('[!] InternetConnectA export not found in wininet.dll');
        return false;
    }

    Interceptor.attach(fnAddr, {
        onEnter(args) {
            try {
                const hostname = args[1].readAnsiString();
                if (hostname === FROM_HOST) {
                    this.redirected   = true;
                    this.originalHost = hostname;
                    this.port         = args[2].toInt32();
                    args[1]           = redirectBuf;
                } else {
                    this.redirected = false;
                }
            } catch (_) {
                this.redirected = false;
            }
        },
        onLeave(retval) {
            if (this.redirected) {
                send(JSON.stringify({
                    event:   'redirect',
                    from:    this.originalHost,
                    to:      TO_HOST,
                    port:    this.port,
                    handle:  retval.toString(),
                    success: !retval.isNull(),
                }));
            }
        }
    });

    hooked = true;
    send('[FTP Redirect v3] Hook installed on InternetConnectA');
    return true;
}

// Try immediately
if (!installHook()) {
    send('[FTP Redirect v3] wininet.dll not loaded yet — watching LoadLibrary');

    const loadFns = ['LoadLibraryA', 'LoadLibraryW', 'LoadLibraryExA', 'LoadLibraryExW'];
    loadFns.forEach(name => {
        const addr = Process.findModuleByName('kernel32.dll');
        if (!addr) return;
        let fn = null;
        try { fn = addr.findExportByName(name); } catch (_) {}
        if (!fn) return;

        Interceptor.attach(fn, {
            onEnter(args) {
                try {
                    this.lib = name.endsWith('W')
                        ? args[0].readUtf16String()
                        : args[0].readAnsiString();
                } catch (_) { this.lib = ''; }
            },
            onLeave(_) {
                if (this.lib && this.lib.toLowerCase().includes('wininet')) {
                    send('[FTP Redirect v3] wininet.dll loaded — installing hook');
                    installHook();
                }
            }
        });
    });
}
