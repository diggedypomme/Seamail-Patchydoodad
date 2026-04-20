# -*- coding: utf-8 -*-
"""
screensaver_overlay_v7.py
--------------------------
v7: SPEECH BUBBLE INJECTION - Attempt to display English translation in bubble
    - Inherits all v6 features (text capture + translation)
    - NEW: Tries to inject English translation into speech bubble via SetBaloonText

NUMBER KEYS (Overlay):
  [0] Enable cursor (re-trigger to apply)
  [1] Exit lock (mouse+click prevent exit)
  [2] Windowed mode (re-trigger to apply)
  [3] Chroma key black->transparent (re-trigger to apply)
  [4] Alpha blend 70% (re-trigger to apply)
  [5] Always on top (live)
  [6] Click-through (live)
  [7] Show in taskbar (live)
  [8] Green screen D3D clear black->green (re-trigger to apply)
  [9] PRESET: 1+2+3+7 windowed overlay

LETTER KEYS (Interactions):
  [Q] Tickle (titillate)
  [W] Spin (guruguru)
  [E] Click left
  [R] Click right
  [T] Click top
  [Y] Click bottom
  [C] Click center
  [F] Double-click center

LETTER KEYS (Menus):
  [M] Memo (81)
  [L] Letter box (82)
  [A] Address book (83)
  [K] Check mail (85)
  [P] Preferences (87)
  [U] Trigger update (92)
  [V] Version screen (93)
  [S] Screensaver (96)
  [D] Open main menu (direct bypass)

SYSTEM:
  [status] Show current state of all toggles
  [inspect] Show all Seaman windows and cursor state
  [move] Move window to new X,Y position
  [movetest] Test-move each window 50px right (identify windows)
  [cursortest] Test if game resets cursor (watch API Monitor)
  [cursorshow] Call ShowCursor(TRUE) once
  [cursorhide] Call ShowCursor(FALSE) once
  [x] Quit (or 'quit', 'exit')
  [?] Help (or 'help')

TEXT CAPTURE + TRANSLATION + BUBBLE INJECTION:
  🗣️  Automatically prints "seaman says: xxxxx" whenever Seaman speaks
  💬 Automatically translates Japanese text to English (non-blocking)
  🎈 Attempts to inject English translation into the speech bubble itself!
  Text is captured from TextOutEx.dll::SetBaloonText and decoded from Shift-JIS

Usage:
  python screensaver_overlay_v7.py
  Type commands and press Enter (e.g., type 's' then Enter to trigger screensaver)
  Watch the speech bubble - does it show English or create a second bubble?
"""
import ctypes
import ctypes.wintypes
import frida
import sys
import time
import asyncio
import threading
from pathlib import Path
from googletrans import Translator

_SUITE = Path(__file__).resolve().parents[1]
if str(_SUITE) not in sys.path:
    sys.path.insert(0, str(_SUITE))
from path_helpers import resolve_game_executable  # noqa: E402

_PROCESS_NAME = resolve_game_executable().name

user32 = ctypes.windll.user32
WM_COMMAND = 0x0111

# Menu IDs
MENU_IDS = {
    'memo': 81,
    'letter_box': 82,
    'address_book': 83,
    'check_mail': 85,
    'preferences': 87,
    'trigger_update': 92,
    'version_screen': 93,
    'screensaver': 96,
}

# Click positions
CLICK_POSITIONS = {
    'left': (300, 400),
    'right': (700, 400),
    'top': (500, 300),
    'bottom': (500, 500),
    'center': (500, 400),
}

# ─── Screensaver trigger ──────────────────────────────────────────────────────

def find_spc_parent():
    main_hwnd = user32.FindWindowW(None, "MainParentForm")
    if not main_hwnd:
        return None
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(main_hwnd, ctypes.byref(pid))
    result = []
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def cb(hwnd, _):
        p = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid.value:
            buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, buf, 256)
            if buf.value == "SPC_Parent":
                result.append(hwnd)
                return False
        return True
    user32.EnumWindows(EnumProc(cb), 0)
    return result[0] if result else None

def send_menu_command(menu_id):
    hwnd = find_spc_parent()
    if not hwnd:
        print("  [-] SPC_Parent not found")
        return False
    user32.PostMessageA(hwnd, WM_COMMAND, menu_id, 0)
    print(f"  [+] Menu command {menu_id} sent")
    return True

# ─── Combined Frida script ────────────────────────────────────────────────────
#
# Combines:
#   1. Overlay (CreateWindowExA hook + D3D8 green screen + exit lock)
#   2. Interactions (brain state machine capture + click/tickle/spin)
#   3. Direct menu (game object capture + menu spawn function)

FRIDA_SCRIPT = """
var user32mod = Module.load('user32.dll');
var seamanModule = Process.enumerateModules()[0];

// ════════════════════════════════════════════════════════════════════════════
// PART 0: CURSOR PATCH (bypass ShowCursor loop with unconditional jump)
// ════════════════════════════════════════════════════════════════════════════

(function() {
    var seamanMod = Process.getModuleByName('Seaman_1_2_57.exe');
    if (!seamanMod) {
        send({ type: 'error', msg: '[Cursor Patch] Seaman.exe not found!' });
        return;
    }
    var baseAddr = seamanMod.base;

    // Target: 0x0043ef34 (start of ShowCursor loop)
    // Patch: push ebp (0x55) → jmp 0x43ef48 (0xEB 0x12)
    // Effect: Skip entire cursor-hiding routine
    var targetAddr = baseAddr.add(0x3ef34);

    // Read original byte
    var origByte = targetAddr.readU8();

    // Verify we're patching the right instruction (0x55 = push ebp)
    if (origByte !== 0x55) {
        send({ type: 'error', msg: '[Cursor Patch] Unexpected byte at 0x3ef34! Expected 0x55, got 0x' + origByte.toString(16) });
        return;
    }

    // Make memory writable
    Memory.protect(targetAddr, 2, 'rwx');

    // Patch: 0x55 (push ebp) → 0xEB 0x12 (jmp short +18)
    // Jump calculation: 0x43ef48 - (0x43ef34 + 2) = 0x12
    targetAddr.writeByteArray([0xEB, 0x12]);

    send({ type: 'success', msg: '[Cursor Patch] ShowCursor loop bypassed - cursor will stay visible!' });
})();

// ════════════════════════════════════════════════════════════════════════════
// PART 1: OVERLAY (screensaver window tweaks)
// ════════════════════════════════════════════════════════════════════════════

var cfg = {
    enableCursor: false,
    windowed:    false,
    chromaKey:   false,
    alpha:       false,
    greenScreen: false,
};

var lastHwnd = null;

var WS_POPUP            = 0x80000000;
var WS_OVERLAPPEDWINDOW = 0x00CF0000;
var WS_EX_LAYERED       = 0x00080000;
var WS_EX_TOOLWINDOW    = 0x00000080;
var WS_EX_APPWINDOW     = 0x00040000;
var LWA_COLORKEY        = 0x00000001;
var LWA_ALPHA           = 0x00000002;

var SetLayeredWindowAttributes = new NativeFunction(
    user32mod.getExportByName('SetLayeredWindowAttributes'),
    'bool', ['pointer', 'uint32', 'uint8', 'uint32']
);
var SetWindowTextA = new NativeFunction(
    user32mod.getExportByName('SetWindowTextA'),
    'bool', ['pointer', 'pointer']
);
var SetWindowPos = new NativeFunction(
    user32mod.getExportByName('SetWindowPos'),
    'bool', ['pointer', 'pointer', 'int', 'int', 'int', 'int', 'uint32']
);
var GetWindowLongA = new NativeFunction(
    user32mod.getExportByName('GetWindowLongA'),
    'int32', ['pointer', 'int32']
);
var SetWindowLongA = new NativeFunction(
    user32mod.getExportByName('SetWindowLongA'),
    'int32', ['pointer', 'int32', 'int32']
);
var SetCursorPos = new NativeFunction(
    user32mod.getExportByName('SetCursorPos'),
    'int', ['int', 'int']
);
var LoadCursorA = new NativeFunction(
    user32mod.getExportByName('LoadCursorA'),
    'pointer', ['pointer', 'pointer']
);
var SetClassLongA = new NativeFunction(
    user32mod.getExportByName('SetClassLongA'),
    'uint32', ['pointer', 'int32', 'uint32']
);
var SetCursor = new NativeFunction(
    user32mod.getExportByName('SetCursor'),
    'pointer', ['pointer']
);
var ShowCursor = new NativeFunction(
    user32mod.getExportByName('ShowCursor'),
    'int', ['int']
);
var GetCursorInfo = new NativeFunction(
    user32mod.getExportByName('GetCursorInfo'),
    'bool', ['pointer']
);

var GCL_HCURSOR = -12;  // GetClassLong index for cursor

// Hook RegisterClassExA to enable cursor
var RegisterClassExA = user32mod.getExportByName('RegisterClassExA');
var cursorEnabled = false;

Interceptor.attach(RegisterClassExA, {
    onEnter: function(args) {
        try {
            var wndclass = args[0];
            // WNDCLASSEXA.lpszClassName at offset 0x28 (x86)
            var classNamePtr = wndclass.add(0x28).readPointer();
            if (!classNamePtr.isNull()) {
                var className = classNamePtr.readUtf8String();
                if (className && className.indexOf('ScreenSaver') !== -1) {
                    if (cfg.enableCursor) {
                        send({ type: 'log', msg: '[*] RegisterClassExA for ScreenSaver - enabling cursor' });
                        // WNDCLASSEXA.hCursor at offset 0x1c (x86)
                        var hCursorPtr = wndclass.add(0x1c);
                        // Load standard arrow cursor (IDC_ARROW = 32512)
                        var hCursor = LoadCursorA(ptr(0), ptr(32512));
                        hCursorPtr.writePointer(hCursor);
                        cursorEnabled = true;
                        send({ type: 'log', msg: '[+] Cursor enabled for screensaver window' });
                    } else {
                        send({ type: 'log', msg: '[*] RegisterClassExA for ScreenSaver - cursor disabled (default)' });
                    }
                }
            }
        } catch(e) {
            send({ type: 'log', msg: '[!] RegisterClassExA hook error: ' + e });
        }
    }
});

// No ShowCursor hook - causes crash loop

// Hook CreateWindowExA for screensaver window
var CreateWindowExA = user32mod.getExportByName('CreateWindowExA');
Interceptor.attach(CreateWindowExA, {
    onEnter: function(args) {
        try {
            var className = args[1].readUtf8String();
            this.isScreensaver = className && className.indexOf('ScreenSaver') !== -1;
        } catch(e) {
            this.isScreensaver = false;
        }

        if (this.isScreensaver) {
            send({ type: 'log', msg: '[*] CreateWindowExA for ScreenSaver' });

            var exStyle = args[0].toInt32() >>> 0;
            var style   = args[3].toInt32() >>> 0;

            if (cfg.chromaKey || cfg.alpha || cfg.greenScreen) {
                exStyle = exStyle | WS_EX_LAYERED;
            }

            if (cfg.windowed) {
                exStyle = (exStyle & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW;
                style = WS_OVERLAPPEDWINDOW;
            }

            args[0] = ptr(exStyle);
            args[3] = ptr(style);

            send({ type: 'log', msg: '[*] Styles: exStyle=0x' + exStyle.toString(16) + ' style=0x' + style.toString(16) });
        }
    },
    onLeave: function(retval) {
        if (this.isScreensaver && !retval.isNull()) {
            lastHwnd = retval;
            send({ type: 'hwnd', value: retval.toString() });
            send({ type: 'log', msg: '[+] Screensaver HWND: ' + retval });

            if (cfg.windowed) {
                SetWindowTextA(retval, Memory.allocUtf8String('Seaman Screensaver'));
            }

            // Enable cursor if requested
            if (cfg.enableCursor) {
                try {
                    // Restore cursor count (game just called ShowCursor(FALSE))
                    var ShowCursor = new NativeFunction(
                        user32mod.getExportByName('ShowCursor'),
                        'int', ['int']
                    );
                    var count = ShowCursor(1);  // Restore from -1 to 0
                    send({ type: 'log', msg: '[+] Cursor restored (count=' + count + ')' });

                    // Also set window class cursor
                    var hCursor = LoadCursorA(ptr(0), ptr(32512));  // IDC_ARROW
                    SetClassLongA(retval, GCL_HCURSOR, hCursor.toInt32() >>> 0);
                    SetCursor(hCursor);
                } catch(e) {
                    send({ type: 'log', msg: '[!] Cursor enable failed: ' + e });
                }
            }

            if (cfg.greenScreen) {
                SetLayeredWindowAttributes(retval, 0x0000FF00, 0, LWA_COLORKEY);
                send({ type: 'log', msg: '[+] Green screen chroma key set' });
            } else if (cfg.chromaKey) {
                SetLayeredWindowAttributes(retval, 0x000000, 0, LWA_COLORKEY);
                send({ type: 'log', msg: '[+] Chroma key (black->transparent)' });
            } else if (cfg.alpha) {
                SetLayeredWindowAttributes(retval, 0, 180, LWA_ALPHA);
                send({ type: 'log', msg: '[+] Alpha blend 70%' });
            }
        }
    }
});

// D3D8 green screen hook
(function() {
    var d3d8mod = Process.findModuleByName('d3d8.dll');
    if (!d3d8mod) {
        send({ type: 'log', msg: '[D3D8] Not loaded yet — green screen will activate when d3d8 loads' });
        return;
    }

    var d3dCreate8Addr = d3d8mod.getExportByName('Direct3DCreate8');
    if (!d3dCreate8Addr) { return; }

    var clearHookInstalled = false;

    function hookClear(devicePtr) {
        if (clearHookInstalled) return;
        clearHookInstalled = true;
        var devVtable = devicePtr.readPointer();
        var clearFn = devVtable.add(36 * 4).readPointer();
        send({ type: 'log', msg: '[D3D8] Hooking Clear at ' + clearFn });
        Interceptor.attach(clearFn, {
            onEnter: function(args) {
                if (!cfg.greenScreen) return;
                var color = args[3].toUInt32();
                if ((color & 0x00FFFFFF) === 0) {
                    args[3] = ptr((color & 0xFF000000) | 0x0000FF00);
                }
            }
        });
    }

    Interceptor.attach(d3dCreate8Addr, {
        onLeave: function(retval) {
            if (retval.isNull()) return;
            var vtable = retval.readPointer();
            var createDeviceFn = vtable.add(15 * 4).readPointer();
            send({ type: 'log', msg: '[D3D8] Hooking CreateDevice' });
            Interceptor.attach(createDeviceFn, {
                onEnter: function(args) {
                    this.ppDevice = args[5];
                },
                onLeave: function(retval) {
                    if (retval.toUInt32() !== 0) return;
                    if (!this.ppDevice || this.ppDevice.isNull()) return;
                    var dev = this.ppDevice.readPointer();
                    if (dev.isNull()) return;
                    send({ type: 'log', msg: '[D3D8] Device captured: ' + dev });
                    hookClear(dev);
                }
            });
        }
    });
    send({ type: 'log', msg: '[D3D8] Direct3DCreate8 hook active' });
})();

// Exit-lock patches
var base = Process.mainModule.base;
var locked = false;
var PATCHES = [
    { name: 'mouse-movement', offset: 0x2295d, orig: [0x75, 0x0e], patch: [0xeb, 0x54] },
    { name: 'click-exit',     offset: 0x22ba3, orig: [0x76, 0x07], patch: [0xeb, 0x3a] },
];
function applyExitLock(enable) {
    for (var i = 0; i < PATCHES.length; i++) {
        var p = PATCHES[i];
        var addr = base.add(p.offset);
        var bytes = enable ? p.patch : p.orig;
        Memory.protect(addr, 4, 'rwx');
        addr.writeU8(bytes[0]);
        addr.add(1).writeU8(bytes[1]);
    }
    locked = enable;
}

// Overlay window tweaks
var GWL_EXSTYLE         = -20;
var WS_EX_TRANSPARENT   = 0x00000020;
var HWND_TOPMOST        = ptr(-1);
var HWND_NOTOPMOST      = ptr(-2);
var SWP_NOMOVE          = 0x0002;
var SWP_NOSIZE          = 0x0001;

function applyTopmost(enable) {
    if (!lastHwnd) { send({ type: 'log', msg: '[-] No screensaver HWND yet' }); return; }
    SetWindowPos(lastHwnd, enable ? HWND_TOPMOST : HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE);
}

function applyTaskbar(enable) {
    if (!lastHwnd) { send({ type: 'log', msg: '[-] No screensaver HWND yet' }); return; }
    var ex = GetWindowLongA(lastHwnd, GWL_EXSTYLE);
    if (enable) {
        ex = (ex & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW;
    } else {
        ex = (ex & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW;
    }
    SetWindowLongA(lastHwnd, GWL_EXSTYLE, ex);
    SetWindowPos(lastHwnd, ptr(0), 0, 0, 0, 0, 0x0027); // FRAMECHANGED
}

function applyClickthrough(enable) {
    if (!lastHwnd) { send({ type: 'log', msg: '[-] No screensaver HWND yet' }); return; }
    var ex = GetWindowLongA(lastHwnd, GWL_EXSTYLE);
    if (enable) {
        SetWindowLongA(lastHwnd, GWL_EXSTYLE, ex | WS_EX_TRANSPARENT);
    } else {
        SetWindowLongA(lastHwnd, GWL_EXSTYLE, ex & ~WS_EX_TRANSPARENT);
    }
}

// ════════════════════════════════════════════════════════════════════════════
// PART 2: INTERACTIONS (brain state machine)
// ════════════════════════════════════════════════════════════════════════════

var brainInstance = null;
var stateHandler = seamanModule.base.add(0x7E60);  // CHigyoBrain::Action
var stateOffset = 0xa4;
var internalStateOffset = 0xa8;

Interceptor.attach(stateHandler, {
    onEnter: function (args) {
        if (brainInstance === null) {
            brainInstance = this.context.ecx;
            send({ type: 'ready', msg: 'Seaman brain captured: ' + brainInstance });
        }
    }
});

// ════════════════════════════════════════════════════════════════════════════
// PART 3: DIRECT MENU (game object capture)
// ════════════════════════════════════════════════════════════════════════════

var mainGameObject = null;
var processClickDispatch = seamanModule.base.add(0x37660);
var handleEmptySpaceClick = seamanModule.base.add(0x39bc0);
var processFrameUpdate = seamanModule.base.add(0x36ba0);
var playOneshotSound = seamanModule.base.add(0x33ce0);

Interceptor.attach(processFrameUpdate, {
    onEnter: function (args) {
        if (mainGameObject === null) {
            mainGameObject = this.context.ecx;
            try {
                var entityListPtr = mainGameObject.add(0x51c).readPointer();
                send({ type: 'ready', msg: 'Game object captured: ' + mainGameObject });
            } catch (e) {}
        }
    }
});

var triggerMenuNative = new NativeFunction(
    handleEmptySpaceClick,
    'void',
    ['pointer'],
    'fastcall'
);

var playClickSound = new NativeFunction(
    playOneshotSound,
    'void',
    ['int']
);

// ════════════════════════════════════════════════════════════════════════════
// RPC EXPORTS
// ════════════════════════════════════════════════════════════════════════════

rpc.exports = {
    // Status
    isReady: function () {
        return brainInstance !== null || mainGameObject !== null;
    },

    getStatus: function () {
        return {
            brain: brainInstance ? brainInstance.toString() : 'not captured',
            gameObj: mainGameObject ? mainGameObject.toString() : 'not captured',
            hwnd: lastHwnd ? lastHwnd.toString() : 'not captured',
            ready: brainInstance !== null || mainGameObject !== null
        };
    },

    // Overlay: Exit lock
    lockToggle:  function() { applyExitLock(!locked); return locked; },
    lockEnable:  function() { applyExitLock(true);  return locked; },
    lockDisable: function() { applyExitLock(false); return locked; },
    lockStatus:  function() { return locked; },

    // Overlay: Creation-time settings
    setEnableCursor: function(v) {
        cfg.enableCursor = v;
        // ShowCursor will be called when screensaver window is created
        return cfg;
    },
    setWindowed:    function(v) { cfg.windowed  = v; return cfg; },
    setChromaKey:   function(v) { cfg.chromaKey = v; if(v) { cfg.alpha = false; cfg.greenScreen = false; } return cfg; },
    setAlpha:       function(v) { cfg.alpha = v; if(v) { cfg.chromaKey = false; cfg.greenScreen = false; } return cfg; },
    setGreenScreen: function(v) { cfg.greenScreen = v; if(v) { cfg.chromaKey = false; cfg.alpha = false; } return cfg; },
    getConfig:      function() { return cfg; },

    // Overlay: Live tweaks
    setTopmost:      function(v) { applyTopmost(v); },
    setClickthrough: function(v) { applyClickthrough(v); },
    setTaskbar:      function(v) { applyTaskbar(v); },

    getHwnd: function() { return lastHwnd ? lastHwnd.toString() : null; },

    // Interactions: Click/tickle/spin
    clickSeaman: function (x, y) {
        if (brainInstance === null) {
            send({ type: 'error', msg: 'Brain not captured!' });
            return false;
        }
        send({ type: 'action', msg: 'Click at (' + x + ', ' + y + ')' });
        try {
            SetCursorPos(x, y);
            Thread.sleep(0.1);
            var stateAddr = brainInstance.add(stateOffset);
            stateAddr.writeU32(0x17);
            Thread.sleep(0.2);
            stateAddr.writeU32(0);
            send({ type: 'success', msg: 'Click triggered!' });
            return true;
        } catch (e) {
            send({ type: 'error', msg: 'Click failed: ' + e });
            return false;
        }
    },

    doubleClickSeaman: function (x, y) {
        if (brainInstance === null) {
            send({ type: 'error', msg: 'Brain not captured!' });
            return false;
        }
        send({ type: 'action', msg: 'Double-click at (' + x + ', ' + y + ')' });
        try {
            SetCursorPos(x, y);
            Thread.sleep(0.1);
            var stateAddr = brainInstance.add(stateOffset);
            // First click
            stateAddr.writeU32(0x17);
            Thread.sleep(0.1);
            stateAddr.writeU32(0);
            Thread.sleep(0.05);
            // Second click
            stateAddr.writeU32(0x17);
            Thread.sleep(0.1);
            stateAddr.writeU32(0);
            send({ type: 'success', msg: 'Double-click triggered!' });
            return true;
        } catch (e) {
            send({ type: 'error', msg: 'Double-click failed: ' + e });
            return false;
        }
    },

    tickleSeaman: function () {
        if (brainInstance === null) {
            send({ type: 'error', msg: 'Brain not captured!' });
            return false;
        }
        send({ type: 'action', msg: 'Tickling...' });
        try {
            var stateAddr = brainInstance.add(stateOffset);
            var internalAddr = brainInstance.add(internalStateOffset);
            internalAddr.writeU32(0);
            stateAddr.writeU32(0x16);
            Thread.sleep(0.5);
            stateAddr.writeU32(0);
            send({ type: 'success', msg: 'Tickle triggered!' });
            return true;
        } catch (e) {
            send({ type: 'error', msg: 'Tickle failed: ' + e });
            return false;
        }
    },

    spinSeaman: function (centerX, centerY, radius) {
        if (brainInstance === null) {
            send({ type: 'error', msg: 'Brain not captured!' });
            return false;
        }
        if (centerX === undefined) centerX = 512;
        if (centerY === undefined) centerY = 384;
        if (radius === undefined) radius = 100;

        send({ type: 'action', msg: 'Spinning at (' + centerX + ', ' + centerY + ')' });
        try {
            var stateAddr = brainInstance.add(stateOffset);
            var internalAddr = brainInstance.add(internalStateOffset);
            internalAddr.writeU32(0);
            stateAddr.writeU32(0x21);

            var steps = 30;
            var duration = 2.0;
            var delayPerStep = duration / steps;

            for (var i = 0; i < steps; i++) {
                var angle = (i / steps) * 2 * Math.PI;
                var x = centerX + Math.cos(angle) * radius;
                var y = centerY + Math.sin(angle) * radius;
                SetCursorPos(Math.round(x), Math.round(y));
                Thread.sleep(delayPerStep);
            }

            stateAddr.writeU32(0);
            send({ type: 'success', msg: 'Spin triggered!' });
            return true;
        } catch (e) {
            send({ type: 'error', msg: 'Spin failed: ' + e });
            return false;
        }
    },

    // Direct menu
    openMenu: function () {
        if (mainGameObject === null) {
            send({ type: 'error', msg: 'Game object not captured!' });
            return false;
        }
        send({ type: 'action', msg: 'Opening menu...' });
        try {
            playClickSound(3);
            triggerMenuNative(mainGameObject);
            send({ type: 'success', msg: 'Menu opened!' });
            return true;
        } catch (e) {
            send({ type: 'error', msg: 'Menu open failed: ' + e });
            return false;
        }
    },

    // Cursor diagnostics
    getCursorCount: function() {
        try {
            // ShowCursor always modifies count, no way to query without changing
            // Just call ShowCursor(TRUE) and it returns the PREVIOUS count
            var prevCount = ShowCursor(1);  // Increment, returns previous
            send({ type: 'log', msg: '[Cursor] ShowCursor(TRUE) returned: ' + prevCount + ' (was ' + prevCount + ', now ' + (prevCount + 1) + ')' });
            return prevCount;
        } catch (e) {
            send({ type: 'error', msg: 'GetCursorCount failed: ' + e });
            return null;
        }
    },

    cursorShow: function() {
        try {
            var count = ShowCursor(1);  // TRUE = show
            send({ type: 'log', msg: '[Cursor] ShowCursor(TRUE) returned: ' + count });
            return count;
        } catch (e) {
            send({ type: 'error', msg: 'ShowCursor(TRUE) failed: ' + e });
            return null;
        }
    },

    cursorHide: function() {
        try {
            var count = ShowCursor(0);  // FALSE = hide
            send({ type: 'log', msg: '[Cursor] ShowCursor(FALSE) returned: ' + count });
            return count;
        } catch (e) {
            send({ type: 'error', msg: 'ShowCursor(FALSE) failed: ' + e });
            return null;
        }
    },

    // Inject English text into speech bubble
    injectBalloonText: function(englishText, param2, param3) {
        if (!setBaloonTextFunc) {
            send({ type: 'error', msg: '[Balloon] SetBaloonText function not available' });
            return false;
        }

        try {
            send({ type: 'log', msg: '[Balloon] Injecting English: "' + englishText + '"' });

            // Allocate memory for the English string
            // NOTE: SetBaloonText expects Shift-JIS encoding
            // For basic ASCII English text, UTF-8 and Shift-JIS are identical
            // If we need special characters, we'll need proper Shift-JIS encoding
            var textPtr = Memory.allocUtf8String(englishText);

            // Set flag to prevent our hook from intercepting this call
            isInjecting = true;

            // Call SetBaloonText with English text and same params as original
            setBaloonTextFunc(textPtr, param2, param3);

            // Clear flag
            isInjecting = false;

            send({ type: 'success', msg: '[Balloon] English text injected!' });
            return true;
        } catch (e) {
            send({ type: 'error', msg: '[Balloon] Injection failed: ' + e });
            return false;
        }
    }
};

// ════════════════════════════════════════════════════════════════════════════
// PART 4: TEXT CAPTURE + BUBBLE INJECTION
// ════════════════════════════════════════════════════════════════════════════

var setBaloonTextPtr = null;
var setBaloonTextFunc = null;
var lastBalloonParams = { param2: 0, param3: 0 };
var isInjecting = false;  // Flag to prevent hook loop when we inject text

var textOutExModule = Process.findModuleByName("TextOutEx.dll");
if (textOutExModule) {
    setBaloonTextPtr = textOutExModule.getExportByName("SetBaloonText");
    if (setBaloonTextPtr) {
        send({ type: 'log', msg: '[Text Hook] Found TextOutEx.dll!SetBaloonText at ' + setBaloonTextPtr });

        // Create NativeFunction wrapper to call it later
        setBaloonTextFunc = new NativeFunction(setBaloonTextPtr, 'void', ['pointer', 'int', 'int']);

        Interceptor.attach(setBaloonTextPtr, {
            onEnter: function (args) {
                // Skip if we're the ones calling it (prevent infinite loop)
                if (isInjecting) {
                    return;
                }

                // SetBaloonText(char* text, int param_2, int balloon_index)
                // args[0] = text pointer (Shift-JIS)
                // args[1] = param_2 (unknown purpose)
                // args[2] = balloon_index
                var pointer = args[0];
                var param2 = args[1].toInt32();
                var param3 = args[2].toInt32();

                // Store params for later use
                lastBalloonParams.param2 = param2;
                lastBalloonParams.param3 = param3;

                if (pointer && !pointer.isNull()) {
                    // Find string length (null-terminated)
                    var len = 0;
                    while (pointer.add(len).readU8() !== 0 && len < 1000) {
                        len++;
                    }
                    // Read raw bytes and send to Python for Shift-JIS decoding
                    // send() takes (payload, data) - data goes to on_message's data param
                    var bytes = pointer.readByteArray(len);
                    send({
                        type: 'speech',
                        param2: param2,
                        param3: param3
                    }, bytes);
                }
            }
        });
    }
} else {
    send({ type: 'log', msg: '[Text Hook] TextOutEx.dll not loaded yet' });
}

send({ type: 'init', msg: 'Unified overlay v7 loaded (cursor + text + translation + BUBBLE INJECTION!)' });
"""

# ─── Main controller ──────────────────────────────────────────────────────────

class UnifiedController:
    def __init__(self):
        self.session = None
        self.script = None
        self.ex = None
        self.running = True
        self.ready = False

        # Overlay states
        self.states = {
            'lock': False,
            'topmost': False,
            'clickthru': False,
            'taskbar': False,
            'hwnd': None
        }

        # Overlay config
        self.cfg = {
            'enableCursor': False,
            'windowed': False,
            'chromaKey': False,
            'alpha': False,
            'greenScreen': False
        }

        # Window inspection state
        self.last_inspection = None

    def on_message(self, message, data):
        """Handle Frida messages"""
        if message['type'] == 'send':
            p = message['payload']
            msg_type = p.get('type', 'info')
            msg_text = p.get('msg', p)

            # Special handling for speech capture
            if msg_type == 'speech':
                if data:
                    # Raw bytes sent via send({ type: 'speech', bytes: ... })
                    try:
                        text_decoded = data.decode('shift-jis', errors='replace')
                        print(f"\n🗣️  seaman says: {text_decoded}")

                        # Extract balloon parameters
                        param2 = p.get('param2', 0)
                        param3 = p.get('param3', 0)

                        # Translate to English in background thread (non-blocking)
                        def translate_async():
                            try:
                                # Create fresh translator for each translation (thread-safe)
                                translator = Translator()
                                # Create a new event loop for this thread
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                try:
                                    # Run the async translation
                                    translation = loop.run_until_complete(
                                        translator.translate(text_decoded, src='ja', dest='en')
                                    )
                                    english_text = translation.text
                                    print(f"    💬 translation: {english_text}")

                                    # Try to inject English into balloon
                                    print(f"    🎈 Attempting to inject into balloon (param2={param2}, param3={param3})...")
                                    try:
                                        result = self.ex.inject_balloon_text(english_text, param2, param3)
                                        if result:
                                            print(f"    ✅ Balloon injection succeeded!\n")
                                        else:
                                            print(f"    ❌ Balloon injection failed\n")
                                    except Exception as inj_err:
                                        print(f"    ❌ Balloon injection error: {inj_err}\n")
                                finally:
                                    loop.close()
                            except Exception as e:
                                print(f"    (translation failed: {e})\n")

                        # Start translation in background thread
                        thread = threading.Thread(target=translate_async, daemon=True)
                        thread.start()

                    except Exception as e:
                        print(f"\n🗣️  seaman says: {data!r} (decode error: {e})\n")
                else:
                    print(f"\n🗣️  seaman says: (no data received)\n")
                return

            prefix = {
                'error': '[ERROR]',
                'success': '[✓]',
                'action': '[→]',
                'debug': '[DEBUG]',
                'warning': '[!]',
                'ready': '[READY]',
                'init': '[INIT]',
                'log': ''
            }.get(msg_type, '[INFO]')

            if msg_type == 'log':
                print(f"  {msg_text}")
            else:
                print(f"{prefix} {msg_text}")

            if msg_type == 'hwnd':
                self.states['hwnd'] = p['value']

            if msg_type == 'ready':
                self.ready = True

        elif message['type'] == 'error':
            print(f"[FRIDA ERROR] {message.get('stack', message)}")

    def attach(self):
        """Attach to Seaman process"""
        print(f"[*] Attaching to {_PROCESS_NAME}...")
        try:
            self.session = frida.attach(_PROCESS_NAME)
        except frida.ProcessNotFoundError:
            print(f"[-] {_PROCESS_NAME} not found. Launch it first.")
            return False

        print("[*] Creating Frida script...")
        try:
            js = FRIDA_SCRIPT.replace("'Seaman_1_2_57.exe'", f"'{_PROCESS_NAME}'")
            self.script = self.session.create_script(js)
        except Exception as e:
            print(f"[!] Failed to create script: {e}")
            return False

        self.script.on('message', self.on_message)

        print("[*] Loading script...")
        try:
            self.script.load()
        except Exception as e:
            print(f"[!] Failed to load script: {e}")
            return False

        self.ex = self.script.exports_sync

        time.sleep(0.5)

        print("[+] Frida attached. Hooks active.")
        print("[*] Waiting for game objects...")

        # Test if isReady exists
        try:
            ready_test = self.ex.is_ready()
            print(f"[DEBUG] isReady() returned: {ready_test}")
        except Exception as e:
            print(f"[!] isReady() failed: {e}")
            print("[!] RPC exports might not be loaded correctly")
            return False

        timeout = 5.0
        start = time.time()
        while time.time() - start < timeout:
            if self.ex.is_ready():
                status = self.ex.get_status()
                print(f"[+] Brain: {status['brain']}")
                print(f"[+] GameObj: {status['gameObj']}")
                return True
            time.sleep(0.1)

        print("[!] Game objects not captured - interact with game first")
        print("[*] Controller active anyway - objects will be captured when game runs")
        return True

    def show_help(self):
        """Display hotkey help"""
        print("\n" + "="*70)
        print("SEAMAN UNIFIED OVERLAY v7 (with bubble injection) - HOTKEY MAP")
        print("="*70)
        print("\nNUMBER KEYS (Overlay):")
        print(f"  [0] Enable cursor               [{self._c('enableCursor')}]")
        print(f"  [1] Exit lock                   [{self._s('lock')}]")
        print("  --- Creation-time (re-trigger screensaver after change) ---")
        print(f"  [2] Windowed mode               [{self._c('windowed')}]")
        print(f"  [3] Chroma key (black->transp)  [{self._c('chromaKey')}]")
        print(f"  [4] Alpha blend (WHOLE window)  [{self._c('alpha')}]")
        print("  --- Live (apply to running window) ---")
        print(f"  [5] Always on top               [{self._s('topmost')}]")
        print(f"  [6] Click-through               [{self._s('clickthru')}]")
        print(f"  [7] Show in taskbar             [{self._s('taskbar')}]")
        print(f"  [8] Green screen                [{self._c('greenScreen')}]")
        print("  [9] PRESET: 1+2+3+7 (windowed overlay)")
        print("\nLETTER KEYS (Interactions):")
        print("  [Q] Tickle (titillate)")
        print("  [W] Spin (guruguru)")
        print("  [E] Click left")
        print("  [R] Click right")
        print("  [T] Click top")
        print("  [Y] Click bottom")
        print("  [C] Click center")
        print("  [F] Double-click center")
        print("\nLETTER KEYS (Menus):")
        print("  [M] Memo (81)")
        print("  [L] Letter box (82)")
        print("  [A] Address book (83)")
        print("  [K] Check mail (85)")
        print("  [P] Preferences (87)")
        print("  [U] Trigger update (92)")
        print("  [V] Version screen (93)")
        print("  [S] Screensaver (96)")
        print("  [D] Open main menu (direct bypass)")
        print("\nSYSTEM:")
        print("  [status] Show current state of all toggles")
        print("  [inspect] Show all Seaman windows and cursor state")
        print("  [move] Move window to new X,Y position")
        print("  [movetest] Test-move each window 50px right (identify windows)")
        print("  [cursortest] Test if game resets cursor (watch API Monitor)")
        print("  [cursorshow] Call ShowCursor(TRUE) once")
        print("  [cursorhide] Call ShowCursor(FALSE) once")
        print("  [testballoon] Test inject English text into balloon")
        print("  [x] Quit (or 'quit', 'exit')")
        print("  [?] Help (or 'help')")
        print("="*70)
        if self.states.get('hwnd'):
            print(f"\n  Screensaver HWND: {self.states['hwnd']}")
        else:
            print("\n  (screensaver not running)")
        print()

    def _s(self, k):
        """Format state ON/OFF"""
        return "ON " if self.states.get(k) else "OFF"

    def _c(self, k):
        """Format config ON/OFF"""
        return "ON " if self.cfg.get(k) else "OFF"

    def show_status(self):
        """Show current state of all toggles"""
        print("\n" + "="*70)
        print("CURRENT STATUS")
        print("="*70)
        print("\nOverlay Configuration (creation-time, re-trigger needed):")
        print(f"  Enable cursor:     {self._c('enableCursor')}")
        print(f"  Windowed mode:     {self._c('windowed')}")
        print(f"  Chroma key:        {self._c('chromaKey')}")
        print(f"  Alpha blend:       {self._c('alpha')}")
        print(f"  Green screen:      {self._c('greenScreen')}")
        print("\nOverlay State (live):")
        print(f"  Exit lock:         {self._s('lock')}")
        print(f"  Always on top:     {self._s('topmost')}")
        print(f"  Click-through:     {self._s('clickthru')}")
        print(f"  Taskbar:           {self._s('taskbar')}")
        if self.states.get('hwnd'):
            print(f"\nScreensaver Window:")
            print(f"  HWND: {self.states['hwnd']}")
        else:
            print(f"\nScreensaver Window: Not running")
        print("="*70)
        print()

    def inspect_windows(self):
        """Inspect all Seaman windows and their cursor state"""
        # Constants
        GCL_HCURSOR = -12
        GWL_STYLE = -16
        GWL_EXSTYLE = -20

        # Find Seaman PID
        main_hwnd = user32.FindWindowW(None, "MainParentForm")
        if not main_hwnd:
            print("[-] MainParentForm not found - is Seaman running?")
            return

        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(main_hwnd, ctypes.byref(pid))
        seaman_pid = pid.value

        print(f"\n[+] Found Seaman process: PID {seaman_pid}")

        # Get cursor friendly names
        def get_cursor_name(hCursor):
            cursors = {
                0: "NULL (hidden)",
                32512: "IDC_ARROW",
                32513: "IDC_IBEAM",
                32514: "IDC_WAIT",
                32515: "IDC_CROSS",
                32516: "IDC_UPARROW",
                32642: "IDC_SIZENWSE",
                32643: "IDC_SIZENESW",
                32644: "IDC_SIZEWE",
                32645: "IDC_SIZENS",
                32646: "IDC_SIZEALL",
                32648: "IDC_NO",
                32649: "IDC_HAND",
                32650: "IDC_APPSTARTING",
            }
            hCursor_int = hCursor & 0xFFFF
            if hCursor_int in cursors:
                return f"{cursors[hCursor_int]}"
            elif hCursor == 0:
                return "NULL"
            else:
                return f"0x{hCursor:x}"

        # Enumerate windows
        windows = {}  # Use dict with class as key for easy comparison

        def enum_callback(hwnd, lParam):
            p = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))

            if p.value == lParam:
                try:
                    # Get class name
                    class_buf = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, class_buf, 256)
                    class_name = class_buf.value

                    # Get title
                    title_buf = ctypes.create_unicode_buffer(256)
                    length = user32.GetWindowTextW(hwnd, title_buf, 256)
                    title = title_buf.value if length > 0 else "(no title)"

                    # Get class cursor
                    hCursor = user32.GetClassLongA(hwnd, GCL_HCURSOR)
                    cursor_name = get_cursor_name(hCursor)

                    # Get window styles
                    style = user32.GetWindowLongA(hwnd, GWL_STYLE)
                    ex_style = user32.GetWindowLongA(hwnd, GWL_EXSTYLE)
                    visible = bool(user32.IsWindowVisible(hwnd))

                    windows[class_name] = {
                        'hwnd': hwnd,
                        'class': class_name,
                        'title': title,
                        'hCursor': hCursor,
                        'cursor_name': cursor_name,
                        'visible': visible,
                        'style': style,
                        'ex_style': ex_style
                    }
                except Exception as e:
                    print(f"[!] Error inspecting window {hex(hwnd)}: {e}")

            return True  # Continue enumeration

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        user32.EnumWindows(EnumWindowsProc(enum_callback), seaman_pid)

        if not windows:
            print("[-] No windows found")
            return

        # Compare with previous inspection if exists
        if self.last_inspection:
            print("\n" + "="*90)
            print("WINDOW STATE COMPARISON")
            print("="*90)

            # Find changes
            current_classes = set(windows.keys())
            prev_classes = set(self.last_inspection.keys())

            new_windows = current_classes - prev_classes
            removed_windows = prev_classes - current_classes
            common_windows = current_classes & prev_classes

            # Show new windows
            if new_windows:
                print("\n[NEW WINDOWS]")
                for cls in sorted(new_windows):
                    win = windows[cls]
                    print(f"  + {cls}")
                    print(f"      Cursor: {win['cursor_name']}")
                    print(f"      Visible: {'Yes' if win['visible'] else 'No'}")

            # Show removed windows
            if removed_windows:
                print("\n[REMOVED WINDOWS]")
                for cls in sorted(removed_windows):
                    win = self.last_inspection[cls]
                    print(f"  - {cls}")
                    print(f"      Was cursor: {win['cursor_name']}")

            # Show changed windows
            changed = []
            for cls in sorted(common_windows):
                curr = windows[cls]
                prev = self.last_inspection[cls]

                changes = []
                if curr['hCursor'] != prev['hCursor']:
                    changes.append(f"cursor: {prev['cursor_name']} → {curr['cursor_name']}")
                if curr['visible'] != prev['visible']:
                    changes.append(f"visible: {prev['visible']} → {curr['visible']}")

                if changes:
                    changed.append((cls, changes))

            if changed:
                print("\n[CHANGED WINDOWS]")
                for cls, changes in changed:
                    print(f"  ≠ {cls}")
                    for change in changes:
                        print(f"      {change}")

            if not new_windows and not removed_windows and not changed:
                print("\n[NO CHANGES]")
                print("  All windows unchanged from previous inspection")

            print("\n" + "="*90)

        else:
            # First inspection - show full list
            print("\n" + "="*90)
            print(f"WINDOW STATE SNAPSHOT ({len(windows)} windows)")
            print("="*90)

        # Show current state summary
        screensaver_windows = [w for w in windows.values() if 'ScreenSaver' in w['class']]

        print("\n[CURRENT STATE]")
        print(f"  Total windows:       {len(windows)}")
        print(f"  ScreenSaver windows: {len(screensaver_windows)}")

        if screensaver_windows:
            print("\n  ScreenSaver Window Details:")
            for w in screensaver_windows:
                print(f"    Class:   {w['class']}")
                print(f"    HWND:    {hex(w['hwnd'])}")
                print(f"    Cursor:  {w['cursor_name']}")
                print(f"    Visible: {'Yes' if w['visible'] else 'No'}")

        # Show cursor distribution
        cursor_counts = {}
        for win in windows.values():
            cursor = win['cursor_name']
            cursor_counts[cursor] = cursor_counts.get(cursor, 0) + 1

        print("\n  Cursor Distribution:")
        for cursor, count in sorted(cursor_counts.items(), key=lambda x: -x[1]):
            print(f"    {cursor}: {count} window(s)")

        print()

        # Save current inspection for next comparison
        self.last_inspection = windows

    def move_window_interactive(self):
        """Interactive window mover"""
        # Find Seaman PID
        main_hwnd = user32.FindWindowW(None, "MainParentForm")
        if not main_hwnd:
            print("[-] MainParentForm not found")
            return

        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(main_hwnd, ctypes.byref(pid))
        seaman_pid = pid.value

        # Enumerate windows
        windows = []

        def enum_callback(hwnd, lParam):
            p = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))

            if p.value == lParam:
                try:
                    class_buf = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, class_buf, 256)
                    class_name = class_buf.value

                    title_buf = ctypes.create_unicode_buffer(256)
                    length = user32.GetWindowTextW(hwnd, title_buf, 256)
                    title = title_buf.value if length > 0 else "(no title)"

                    rect = ctypes.wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))

                    visible = bool(user32.IsWindowVisible(hwnd))

                    windows.append({
                        'hwnd': hwnd,
                        'class': class_name,
                        'title': title,
                        'x': rect.left,
                        'y': rect.top,
                        'width': rect.right - rect.left,
                        'height': rect.bottom - rect.top,
                        'visible': visible
                    })
                except:
                    pass

            return True

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        user32.EnumWindows(EnumWindowsProc(enum_callback), seaman_pid)

        if not windows:
            print("[-] No windows found")
            return

        # List windows
        print("\n" + "="*90)
        print("SELECT WINDOW TO MOVE")
        print("="*90)

        for i, win in enumerate(windows, 1):
            vis = "VIS" if win['visible'] else "HID"
            print(f"[{i:2d}] {vis} | {win['class'][:40]:<40} | Pos: ({win['x']:4d}, {win['y']:4d})")

        print("="*90)

        # Get selection
        try:
            choice = input("\nWindow number (or Enter to cancel): ").strip()
            if not choice:
                print("[*] Cancelled")
                return

            win_num = int(choice)
            if win_num < 1 or win_num > len(windows):
                print(f"[!] Invalid number. Choose 1-{len(windows)}")
                return
        except ValueError:
            print("[!] Invalid input")
            return

        selected_win = windows[win_num - 1]
        print(f"\n[*] Selected: {selected_win['class']}")
        print(f"    Current: ({selected_win['x']}, {selected_win['y']})")

        # Get new coordinates
        try:
            new_x = int(input("New X: ").strip())
            new_y = int(input("New Y: ").strip())
        except ValueError:
            print("[!] Invalid coordinates")
            return

        # Move window
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004

        result = user32.SetWindowPos(
            selected_win['hwnd'],
            None,
            new_x,
            new_y,
            0, 0,
            SWP_NOSIZE | SWP_NOZORDER
        )

        if result:
            print(f"[+] Moved to ({new_x}, {new_y})")
        else:
            print("[-] Move failed")

    def move_window_test(self):
        """Move each window 50px right, one at a time, to identify them"""
        # Find Seaman PID
        main_hwnd = user32.FindWindowW(None, "MainParentForm")
        if not main_hwnd:
            print("[-] MainParentForm not found")
            return

        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(main_hwnd, ctypes.byref(pid))
        seaman_pid = pid.value

        # Enumerate windows
        windows = []

        def enum_callback(hwnd, lParam):
            p = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))

            if p.value == lParam:
                try:
                    class_buf = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, class_buf, 256)
                    class_name = class_buf.value

                    title_buf = ctypes.create_unicode_buffer(256)
                    length = user32.GetWindowTextW(hwnd, title_buf, 256)
                    title = title_buf.value if length > 0 else "(no title)"

                    rect = ctypes.wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))

                    visible = bool(user32.IsWindowVisible(hwnd))

                    windows.append({
                        'hwnd': hwnd,
                        'class': class_name,
                        'title': title,
                        'x': rect.left,
                        'y': rect.top,
                        'width': rect.right - rect.left,
                        'height': rect.bottom - rect.top,
                        'visible': visible
                    })
                except:
                    pass

            return True

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        user32.EnumWindows(EnumWindowsProc(enum_callback), seaman_pid)

        if not windows:
            print("[-] No windows found")
            return

        # List windows
        print("\n" + "="*90)
        print(f"MOVE TEST - {len(windows)} windows found")
        print("="*90)
        print("Each window will move 50px right. Press Enter to move to next window.")
        print("="*90)
        print()

        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004

        for i, win in enumerate(windows, 1):
            vis = "VIS" if win['visible'] else "HID"
            print(f"\n[{i}/{len(windows)}] {vis} | Class: {win['class']}")
            print(f"        Title: {win['title']}")
            print(f"        Current position: ({win['x']}, {win['y']})")

            # Move window 50px right
            new_x = win['x'] + 50
            result = user32.SetWindowPos(
                win['hwnd'],
                None,
                new_x,
                win['y'],
                0, 0,
                SWP_NOSIZE | SWP_NOZORDER
            )

            if result:
                print(f"        → Moved to ({new_x}, {win['y']})")
            else:
                print(f"        [!] Move failed")

            if i < len(windows):
                input("        Press Enter for next window...")
            else:
                print("\n[+] Test complete!")
                print("="*90)

    def process_command(self, cmd):
        """Process a command string"""
        cmd = cmd.strip().lower()

        if not cmd:
            return True

        try:
            # HELP
            if cmd == '?' or cmd == 'help':
                self.show_help()

            # STATUS
            elif cmd == 'status' or cmd == 'state':
                self.show_status()

            # INSPECT WINDOWS
            elif cmd == 'inspect' or cmd == 'windows':
                self.inspect_windows()

            # MOVE WINDOW
            elif cmd == 'move':
                self.move_window_interactive()

            # MOVE TEST
            elif cmd == 'movetest':
                self.move_window_test()

            # CURSOR DIAGNOSTICS
            elif cmd in ('cursor', 'cursorstat', 'cursorstatus'):
                print("\n[*] Querying cursor display count...")
                count = self.ex.get_cursor_count()
                if count is not None:
                    state = "VISIBLE" if count >= 0 else "HIDDEN"
                    print(f"[+] Cursor count: {count} ({state})")
                else:
                    print("[-] Failed to get cursor count")

            elif cmd in ('cursorshow', 'cshow'):
                print("\n[*] Calling ShowCursor(TRUE)...")
                count = self.ex.cursor_show()
                if count is not None:
                    print(f"[+] ShowCursor(TRUE) returned: {count}")
                else:
                    print("[-] ShowCursor(TRUE) failed")

            elif cmd in ('cursorhide', 'chide'):
                print("\n[*] Calling ShowCursor(FALSE)...")
                count = self.ex.cursor_hide()
                if count is not None:
                    print(f"[+] ShowCursor(FALSE) returned: {count}")
                else:
                    print("[-] ShowCursor(FALSE) failed")

            elif cmd in ('cursortest', 'ctest'):
                print("\n" + "="*70)
                print("CURSOR DIAGNOSTIC TEST")
                print("="*70)
                print("[*] Testing if game actively resets cursor count...")
                print("[*] Watch API Monitor to see the full sequence\n")

                print("Step 1: Call ShowCursor(TRUE) to set count to 0")
                prev1 = self.ex.cursor_show()
                if prev1 is not None:
                    print(f"    → Returned {prev1} (count was {prev1}, now {prev1 + 1})")
                else:
                    print("    [!] Failed")
                    return True

                import time
                time.sleep(0.5)  # Brief delay

                print("\nStep 2: Call ShowCursor(TRUE) again to check if game reset it")
                prev2 = self.ex.cursor_show()
                if prev2 is not None:
                    print(f"    → Returned {prev2} (count was {prev2}, now {prev2 + 1})")
                else:
                    print("    [!] Failed")
                    return True

                print("\n[*] Analysis:")
                if prev1 == -1 and prev2 == 0:
                    print("    ✓ Count stayed at 0 - game did NOT reset it")
                elif prev1 == -1 and prev2 == -1:
                    print("    ✗ Count was reset from 0 to -1 - game IS actively resetting!")
                elif prev2 == 1:
                    print("    ✓ Count increased to 1 (normal increment)")
                else:
                    print(f"    ? Unexpected: {prev1} → {prev2}")

                print("\n[*] Check API Monitor for ShowCursor calls between steps")
                print("="*70)

            # TEST BALLOON INJECTION
            elif cmd in ('testballoon', 'testb', 'balloon'):
                print("\n" + "="*70)
                print("BALLOON INJECTION TEST")
                print("="*70)
                print("[*] Attempting to inject test English text into balloon...")
                print("[*] This will use the parameters from the last speech bubble")
                try:
                    test_text = "TEST: This is injected English text!"
                    result = self.ex.inject_balloon_text(test_text, 0, 0)
                    if result:
                        print(f"[+] Test balloon injected successfully!")
                        print(f"    Text: \"{test_text}\"")
                        print(f"[*] Check the game - did a balloon appear with English text?")
                    else:
                        print(f"[-] Test balloon injection failed")
                except Exception as e:
                    print(f"[!] Error: {e}")
                print("="*70)

            # EXIT
            elif cmd in ('x', 'quit', 'exit'):
                print("\n[*] Exiting...")
                self.running = False
                return False

            # NUMBER KEYS (Overlay)
            elif cmd == '0':
                self.cfg['enableCursor'] = not self.cfg['enableCursor']
                self.ex.set_enable_cursor(self.cfg['enableCursor'])
                print(f"[0] Enable cursor: {self._c('enableCursor')} (re-trigger to apply)")

            elif cmd == '1':
                self.states['lock'] = bool(self.ex.lock_toggle())
                print(f"[1] Exit lock: {self._s('lock')}")

            elif cmd == '2':
                self.cfg['windowed'] = not self.cfg['windowed']
                self.ex.set_windowed(self.cfg['windowed'])
                print(f"[2] Windowed: {self._c('windowed')} (re-trigger to apply)")

            elif cmd == '3':
                self.cfg['chromaKey'] = not self.cfg['chromaKey']
                if self.cfg['chromaKey']:
                    self.cfg['alpha'] = False
                    self.cfg['greenScreen'] = False
                self.ex.set_chroma_key(self.cfg['chromaKey'])
                print(f"[3] Chroma key: {self._c('chromaKey')} (re-trigger to apply)")

            elif cmd == '4':
                self.cfg['alpha'] = not self.cfg['alpha']
                if self.cfg['alpha']:
                    self.cfg['chromaKey'] = False
                    self.cfg['greenScreen'] = False
                self.ex.set_alpha(self.cfg['alpha'])
                print(f"[4] Alpha blend: {self._c('alpha')} (re-trigger to apply)")

            elif cmd == '5':
                self.states['topmost'] = not self.states['topmost']
                self.ex.set_topmost(self.states['topmost'])
                print(f"[5] Always on top: {self._s('topmost')}")

            elif cmd == '6':
                self.states['clickthru'] = not self.states['clickthru']
                self.ex.set_clickthrough(self.states['clickthru'])
                print(f"[6] Click-through: {self._s('clickthru')}")

            elif cmd == '7':
                self.states['taskbar'] = not self.states['taskbar']
                self.ex.set_taskbar(self.states['taskbar'])
                print(f"[7] Taskbar: {self._s('taskbar')}")

            elif cmd == '8':
                self.cfg['greenScreen'] = not self.cfg['greenScreen']
                if self.cfg['greenScreen']:
                    self.cfg['chromaKey'] = False
                    self.cfg['alpha'] = False
                self.ex.set_green_screen(self.cfg['greenScreen'])
                print(f"[8] Green screen: {self._c('greenScreen')} (re-trigger to apply)")

            elif cmd == '9':
                # Preset
                self.states['lock'] = bool(self.ex.lock_enable())
                self.cfg['windowed'] = True
                self.cfg['chromaKey'] = True
                self.cfg['alpha'] = False
                self.cfg['greenScreen'] = False
                self.ex.set_windowed(True)
                self.ex.set_chroma_key(True)
                self.states['taskbar'] = True
                self.ex.set_taskbar(True)
                print("[9] PRESET ON: exit lock + windowed + chroma + taskbar")
                print("    (type 's' and Enter to trigger screensaver)")

            # LETTER KEYS (Interactions)
            elif cmd == 'q':
                print("[Q] Tickle")
                self.ex.tickle_seaman()

            elif cmd == 'w':
                print("[W] Spin")
                self.ex.spin_seaman(512, 384, 100)

            elif cmd == 'e':
                print("[E] Click left")
                pos = CLICK_POSITIONS['left']
                self.ex.click_seaman(pos[0], pos[1])

            elif cmd == 'r':
                print("[R] Click right")
                pos = CLICK_POSITIONS['right']
                self.ex.click_seaman(pos[0], pos[1])

            elif cmd == 't':
                print("[T] Click top")
                pos = CLICK_POSITIONS['top']
                self.ex.click_seaman(pos[0], pos[1])

            elif cmd == 'y':
                print("[Y] Click bottom")
                pos = CLICK_POSITIONS['bottom']
                self.ex.click_seaman(pos[0], pos[1])

            elif cmd == 'c':
                print("[C] Click center")
                pos = CLICK_POSITIONS['center']
                self.ex.click_seaman(pos[0], pos[1])

            elif cmd == 'f':
                print("[F] Double-click center")
                pos = CLICK_POSITIONS['center']
                self.ex.double_click_seaman(pos[0], pos[1])

            # LETTER KEYS (Menus)
            elif cmd == 'm':
                print("[M] Memo")
                send_menu_command(MENU_IDS['memo'])

            elif cmd == 'l':
                print("[L] Letter box")
                send_menu_command(MENU_IDS['letter_box'])

            elif cmd == 'a':
                print("[A] Address book")
                send_menu_command(MENU_IDS['address_book'])

            elif cmd == 'k':
                print("[K] Check mail")
                send_menu_command(MENU_IDS['check_mail'])

            elif cmd == 'p':
                print("[P] Preferences")
                send_menu_command(MENU_IDS['preferences'])

            elif cmd == 'u':
                print("[U] Trigger update")
                send_menu_command(MENU_IDS['trigger_update'])

            elif cmd == 'v':
                print("[V] Version screen")
                send_menu_command(MENU_IDS['version_screen'])

            elif cmd == 's':
                print("[S] Screensaver")
                send_menu_command(MENU_IDS['screensaver'])

            elif cmd == 'd':
                print("[D] Open main menu (direct)")
                self.ex.open_menu()

            else:
                print(f"[!] Unknown command: {cmd}")

        except Exception as e:
            print(f"[!] Error processing command: {e}")

        return True

    def run(self):
        """Main loop"""
        if not self.attach():
            return 1

        self.show_help()

        print("[*] Controller active - type commands and press Enter")
        print("[*] Type 'x', 'quit', or 'exit' to exit, '?' for help\n")

        # Main input loop
        while self.running:
            try:
                cmd = input("> ").strip()
                if not self.process_command(cmd):
                    break
            except (EOFError, KeyboardInterrupt):
                print("\n[*] Interrupted")
                break
            except Exception as e:
                print(f"[!] Error: {e}")

        print("[*] Reverting exit lock and detaching...")
        try:
            self.ex.lock_disable()
        except Exception:
            pass
        self.session.detach()
        print("[+] Done.")
        return 0

def main():
    controller = UnifiedController()
    return controller.run()

if __name__ == '__main__':
    sys.exit(main())
