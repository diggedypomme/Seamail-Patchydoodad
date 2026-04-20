# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
import ctypes
import ctypes.wintypes
import sys
import math
import os
from pathlib import Path
from PIL import Image, ImageTk
import frida
import time
import threading
import asyncio
from googletrans import Translator

_SUITE = Path(__file__).resolve().parents[1]
if str(_SUITE) not in sys.path:
    sys.path.insert(0, str(_SUITE))
from path_helpers import resolve_game_executable  # noqa: E402

_PROCESS_NAME = resolve_game_executable().name

user32 = ctypes.windll.user32
WM_COMMAND = 0x0111

FRIDA_SCRIPT = """
var user32mod = Module.load('user32.dll');
var seamanModule = Process.enumerateModules()[0];

// ════════════════════════════════════════════════════════════════════════════
// PART 0: CURSOR PATCH (bypass ShowCursor loop)
// ════════════════════════════════════════════════════════════════════════════
(function() {
    var seamanMod = Process.getModuleByName('Seaman_1_2_57.exe');
    if (!seamanMod) return;
    var targetAddr = seamanMod.base.add(0x3ef34);
    if (targetAddr.readU8() === 0x55) {
        Memory.protect(targetAddr, 2, 'rwx');
        targetAddr.writeByteArray([0xEB, 0x12]);
        send({ type: 'log', msg: '[Cursor Patch] SHOWCURSOR loop bypassed!' });
    }
})();

// ════════════════════════════════════════════════════════════════════════════
// PART 1: OVERLAY (hooks)
// ════════════════════════════════════════════════════════════════════════════
var cfg = { enableCursor: true, windowed: false, chromaKey: false, greenScreen: false };
var lastHwnd = null;
var WS_EX_LAYERED = 0x00080000;
var WS_EX_TOOLWINDOW = 0x00000080;
var WS_EX_APPWINDOW = 0x00040000;
var WS_OVERLAPPEDWINDOW = 0x00CF0000;
var LWA_COLORKEY = 1;

var SetLayeredWindowAttributes = new NativeFunction(user32mod.getExportByName('SetLayeredWindowAttributes'), 'bool', ['pointer', 'uint32', 'uint8', 'uint32']);
var SetWindowTextA = new NativeFunction(user32mod.getExportByName('SetWindowTextA'), 'bool', ['pointer', 'pointer']);
var LoadCursorA = new NativeFunction(user32mod.getExportByName('LoadCursorA'), 'pointer', ['pointer', 'pointer']);
var SetClassLongA = new NativeFunction(user32mod.getExportByName('SetClassLongA'), 'uint32', ['pointer', 'int32', 'uint32']);
var SetCursor = new NativeFunction(user32mod.getExportByName('SetCursor'), 'pointer', ['pointer']);
var ShowCursor = new NativeFunction(user32mod.getExportByName('ShowCursor'), 'int', ['int']);
var SetCursorPos = new NativeFunction(user32mod.getExportByName('SetCursorPos'), 'bool', ['int', 'int']);

var locked = false;
var PATCHES = [{ offset: 0x2295d, orig: [0x75, 0x0e], patch: [0xeb, 0x54] }, { offset: 0x22ba3, orig: [0x76, 0x07], patch: [0xeb, 0x3a] }];

function applyExitLock(enable) {
    var base = Process.mainModule.base;
    for (var i = 0; i < PATCHES.length; i++) {
        var p = PATCHES[i]; var addr = base.add(p.offset);
        Memory.protect(addr, 4, 'rwx');
        var bytes = enable ? p.patch : p.orig;
        addr.writeU8(bytes[0]); addr.add(1).writeU8(bytes[1]);
    }
    locked = enable;
}

if (seamanModule) {
    var seamanBase = seamanModule.base;
    var triggerMenuNative = new NativeFunction(seamanBase.add(0x39bc0), 'void', ['pointer'], 'fastcall');
    var playClickSound = new NativeFunction(seamanBase.add(0x33ce0), 'void', ['int']);
    var mainGameObject = null;
    var brainInstance = null;
    var stateOffset = 0xa4;
    var internalStateOffset = 0xa8;

    Interceptor.attach(seamanBase.add(0x36ba0), {
        onEnter: function(args) { if (mainGameObject === null) { mainGameObject = this.context.ecx; send({ type: 'ready' }); } }
    });

    Interceptor.attach(seamanBase.add(0x7E60), {
        onEnter: function(args) { if (brainInstance === null) { brainInstance = this.context.ecx; } }
    });

    // Translation Hook
    var textOutEx = Process.findModuleByName("TextOutEx.dll");
    var setBaloonTextFunc = null;
    var isInjecting = false;
    if (textOutEx) {
        var setBaloonTextPtr = textOutEx.getExportByName("SetBaloonText");
        if (setBaloonTextPtr) {
            setBaloonTextFunc = new NativeFunction(setBaloonTextPtr, 'void', ['pointer', 'int', 'int']);
            Interceptor.attach(setBaloonTextPtr, {
                onEnter: function(args) {
                    if (isInjecting) return;
                    var ptr = args[0];
                    if (ptr && !ptr.isNull()) {
                        var len = 0; while (ptr.add(len).readU8() !== 0 && len < 1000) len++;
                        send({ type: 'speech', p2: args[1].toInt32(), p3: args[2].toInt32() }, ptr.readByteArray(len));
                    }
                }
            });
        }
    }

    // Window Style Hooks
    var CreateWindowExA = user32mod.getExportByName('CreateWindowExA');
    Interceptor.attach(CreateWindowExA, {
        onEnter: function(args) {
            try { var name = args[1].readUtf8String(); this.isSS = name && name.indexOf('ScreenSaver') !== -1; } catch(e) { this.isSS = false; }
            if (this.isSS) {
                var ex = args[0].toInt32() >>> 0; var style = args[3].toInt32() >>> 0;
                if (cfg.chromaKey || cfg.greenScreen) ex |= WS_EX_LAYERED;
                if (cfg.windowed) { ex = (ex & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW; style = WS_OVERLAPPEDWINDOW; }
                args[0] = ptr(ex); args[3] = ptr(style);
            }
        },
        onLeave: function(retval) {
            if (this.isSS && !retval.isNull()) {
                lastHwnd = retval;
                if (cfg.windowed) SetWindowTextA(retval, Memory.allocUtf8String('Seaman Screensaver'));
                if (cfg.greenScreen) SetLayeredWindowAttributes(retval, 0x0000FF00, 0, LWA_COLORKEY);
                else if (cfg.chromaKey) SetLayeredWindowAttributes(retval, 0x00000000, 0, LWA_COLORKEY);
                if (cfg.enableCursor) { ShowCursor(1); var h = LoadCursorA(ptr(0), ptr(32512)); SetClassLongA(retval, -12, h.toInt32() >>> 0); SetCursor(h); }
            }
        }
    });

    // RegisterClass Hook (Cursor fix)
    var RegisterClassExA = user32mod.getExportByName('RegisterClassExA');
    Interceptor.attach(RegisterClassExA, {
        onEnter: function(args) {
            try {
                var w = args[0]; var namePtr = w.add(0x28).readPointer();
                if (!namePtr.isNull() && namePtr.readUtf8String().indexOf('ScreenSaver') !== -1 && cfg.enableCursor) {
                    w.add(0x1c).writePointer(LoadCursorA(ptr(0), ptr(32512)));
                }
            } catch(e) {}
        }
    });
}

rpc.exports = {
    openMenu: function() { if (mainGameObject) { if (playClickSound) try { playClickSound(3); } catch(e) {} triggerMenuNative(mainGameObject); return true; } return false; },
    lockEnable: function() { applyExitLock(true); return true; },
    setWindowed: function(v) { cfg.windowed = v; return true; },
    setChromaKey: function(v) { cfg.chromaKey = v; return true; },
    injectBalloonText: function(text, p2, p3) { if (!setBaloonTextFunc) return false; isInjecting = true; try { setBaloonTextFunc(Memory.allocUtf8String(text), p2, p3); } finally { isInjecting = false; } return true; },
    tickleSeaman: function() {
        if (!brainInstance) return false;
        var stateAddr = brainInstance.add(stateOffset);
        var internalAddr = brainInstance.add(internalStateOffset);
        internalAddr.writeU32(0);
        stateAddr.writeU32(0x16);
        return true;
    },
    spinSeaman: function() {
        if (!brainInstance) return false;
        var stateAddr = brainInstance.add(stateOffset);
        var internalAddr = brainInstance.add(internalStateOffset);
        internalAddr.writeU32(0);
        stateAddr.writeU32(0x21);
        return true;
    }
};
"""

MENU_IDS = {
    'memo': 81,
    'letter_box': 82,
    'address_book': 83,
    'check_mail': 85,
    'preferences': 87,
    'trigger_update': 92,
    'screensaver': 96
    }
IMG_DIR = os.path.join(os.path.dirname(__file__), "images")


BUTTON_LAYOUT = [
    {'id': 81, 'img': 'embedded_028_36x36.png'},
    {'id': 85, 'img': 'embedded_006_36x36.png'},
    {'id': 83, 'img': 'embedded_013_36x36.png'},
    {'id': 87, 'img': 'embedded_011_36x36.png'},
    {'id': 82, 'img': 'embedded_009_36x36.png'},
    {'id': 93, 'img': 'embedded_048_36x36.png'} #changed to version screen
    ]

class MenuOverlay:
    def __init__(self):
        self.root = tk.Tk(); self.root.title("Seaman Menu Overlay v10")
        self.session = None; self.script = None; self.ex = None
        self.root.overrideredirect(True); self.root.attributes('-topmost', True)
        self.game_hwnd = self.find_main(); self.translator = Translator()
        if not self.game_hwnd: self.root.destroy(); return
        rect = ctypes.wintypes.RECT(); user32.GetWindowRect(self.game_hwnd, ctypes.byref(rect))
        self.game_x, self.game_y = rect.left, rect.top; self.game_w, self.game_h = rect.right-rect.left, rect.bottom-rect.top
        self.root.geometry(f"{self.game_w}x{self.game_h}+{self.game_x}+{self.game_y}")
        self.canvas = tk.Canvas(self.root, bg='#FF00FF', highlightthickness=0); self.canvas.pack(fill=tk.BOTH, expand=True)
        self.root.update(); self.apply_ct(); self.center_x, self.center_y = self.game_w//2, self.game_h//2-140
        self.images = {}; self.img_items = {}; self.create_ui(); self.attach_frida(); self.on_enable(None)

    def apply_ct(self):
        hwnd = int(self.root.wm_frame(), 16)
        user32.SetWindowLongW(hwnd, -20, user32.GetWindowLongW(hwnd, -20) | 0x80000)
        user32.SetLayeredWindowAttributes(hwnd, 0x00FF00FF, 0, 0x1)

    def find_main(self):
        main = user32.FindWindowW(None, "MainParentForm")
        pid = ctypes.wintypes.DWORD(); user32.GetWindowThreadProcessId(main, ctypes.byref(pid))
        res = []
        def cb(h, lp):
            p = ctypes.wintypes.DWORD(); user32.GetWindowThreadProcessId(h, ctypes.byref(p))
            if p.value == lp:
                buf = ctypes.create_unicode_buffer(256); user32.GetClassNameW(h, buf, 256)
                if buf.value == "TMainParentForm": res.append(h); return False
            return True
        user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)(cb), pid.value)
        return res[0] if res else None

    def create_ui(self):
        for i, b in enumerate(BUTTON_LAYOUT):
            dx, dy = self.calc_pos(i); x, y = self.center_x+dx, self.center_y+dy
            try:
                color_img = Image.open(os.path.join(IMG_DIR, b['img'])).convert("RGBA")
                alpha = color_img.split()[3]
                gray_l = color_img.convert("L")
                gray_img = Image.merge("RGBA", (gray_l, gray_l, gray_l, alpha))
                tk_color = ImageTk.PhotoImage(color_img)
                tk_gray  = ImageTk.PhotoImage(gray_img)
                self.images[b['id']] = {'color': tk_color, 'gray': tk_gray}
                self.canvas.create_oval(x-20, y-20, x+20, y+20, fill='#222222', outline='#ffffff', tags=f"b_{b['id']}")
                item = self.canvas.create_image(x, y, image=tk_gray, tags=f"b_{b['id']}")
                self.img_items[b['id']] = item
                self.canvas.tag_bind(f"b_{b['id']}", '<Button-1>', lambda e, mid=b['id']: self.on_click(mid))
                self.canvas.tag_bind(f"b_{b['id']}", '<Enter>', lambda e, mid=b['id']: self.canvas.itemconfig(self.img_items[mid], image=self.images[mid]['color']))
                self.canvas.tag_bind(f"b_{b['id']}", '<Leave>', lambda e, mid=b['id']: self.canvas.itemconfig(self.img_items[mid], image=self.images[mid]['gray']))
            except Exception as e: print(f"[!] Button {b['id']} ({b['img']}): {e}")
        self.canvas.create_oval(self.center_x-10, self.center_y-10, self.center_x+10, self.center_y+10, fill='#888888', outline='#ffffff', tags='drag')
        self.canvas.tag_bind('drag', '<Button-1>', self.on_ds); self.canvas.tag_bind('drag', '<B1-Motion>', self.on_dm)
        try:
            ex_img = Image.open(os.path.join(IMG_DIR, 'embedded_016_11x11.png')).convert("RGBA")
            self.exit_img = ImageTk.PhotoImage(ex_img)
            ex_x, ex_y = self.center_x + 93, self.center_y - 62
            self.canvas.create_image(ex_x, ex_y, image=self.exit_img, tags='exit_btn')
            self.canvas.tag_bind('exit_btn', '<Button-1>', self.on_exit)
        except Exception as e: print(f"[!] Exit diamond: {e}")
        self.extra_imgs = []
        row_y = self.center_y + 100
        row_actions = [self.on_tickle, self.on_menu, self.on_spin]
        for j, fname in enumerate(['embedded_032_40x40.png', 'embedded_004_36x36.png', 'embedded_034_40x40.png']):
            row_x = self.center_x + (j - 1) * 50
            tag = f"extra_{j}"
            try:
                color_img = Image.open(os.path.join(IMG_DIR, fname)).convert("RGBA")
                alpha = color_img.split()[3]
                gray_l = color_img.convert("L")
                gray_img = Image.merge("RGBA", (gray_l, gray_l, gray_l, alpha))
                tk_color = ImageTk.PhotoImage(color_img)
                tk_gray  = ImageTk.PhotoImage(gray_img)
                self.extra_imgs.append({'color': tk_color, 'gray': tk_gray})
                idx = len(self.extra_imgs) - 1
                self.canvas.create_oval(row_x-20, row_y-20, row_x+20, row_y+20, fill='#222222', outline='#ffffff', tags=tag)
                item = self.canvas.create_image(row_x, row_y, image=tk_gray, tags=tag)
                self.canvas.tag_bind(tag, '<Button-1>', row_actions[j])
                self.canvas.tag_bind(tag, '<Enter>', lambda e, i=idx, t=tag: self.canvas.itemconfig(self.canvas.find_withtag(t)[-1], image=self.extra_imgs[i]['color']))
                self.canvas.tag_bind(tag, '<Leave>', lambda e, i=idx, t=tag: self.canvas.itemconfig(self.canvas.find_withtag(t)[-1], image=self.extra_imgs[i]['gray']))
            except Exception as e: print(f"[!] Extra button {fname}: {e}")
        try:
            def load_anim(n):
                img = Image.open(os.path.join(IMG_DIR, f'Bitmap{n}.png')).convert("RGBA")
                w, h = img.size
                img = img.resize((int(w * 0.75), int(h * 0.75)), Image.NEAREST)
                return ImageTk.PhotoImage(img)
            self.anim_frames = [load_anim(n) for n in range(114, 120)]
            self.anim_idx = 0
            self.anim_dir = 1
            anim_x, anim_y = self.center_x, self.center_y + 160
            self.anim_item = self.canvas.create_image(anim_x, anim_y, image=self.anim_frames[0], tags='anim_btn')
            self.canvas.tag_bind('anim_btn', '<Button-1>', self.on_enable)
            self._animate()
        except Exception as e: print(f"[!] Anim button: {e}")
        y = self.game_h - 30; cx = self.center_x
        #self.btn(cx+20, y, "OPEN MENU", '#2a8a5a', 'm', self.on_menu)

    def btn(self, x, y, txt, col, tag, cmd):
        self.canvas.create_rectangle(x-40, y-15, x+40, y+15, fill=col, outline='white', tags=tag)
        self.canvas.create_text(x, y, text=txt, fill='white', font=('Arial', 7, 'bold'), tags=tag)
        self.canvas.tag_bind(tag, '<Button-1>', cmd)

    def calc_pos(self, i):
        a = math.radians(-90 + (i * 360 / 6))
        return int(50 * math.cos(a)), int(50 * math.sin(a))

    def on_click(self, mid):
        main = user32.FindWindowW(None, "MainParentForm")
        pid = ctypes.wintypes.DWORD(); user32.GetWindowThreadProcessId(main, ctypes.byref(pid))
        def cb(h, lp):
            p = ctypes.wintypes.DWORD(); user32.GetWindowThreadProcessId(h, ctypes.byref(p))
            if p.value == lp:
                buf = ctypes.create_unicode_buffer(256); user32.GetClassNameW(h, buf, 256)
                if buf.value == "SPC_Parent": user32.PostMessageA(h, WM_COMMAND, mid, 0); return False
            return True
        user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)(cb), pid.value)

    def _animate(self):
        if not hasattr(self, 'anim_frames'): return
        self.anim_idx += self.anim_dir
        if self.anim_idx >= len(self.anim_frames) - 1:
            self.anim_idx = len(self.anim_frames) - 1
            self.anim_dir = -1
        elif self.anim_idx <= 0:
            self.anim_idx = 0
            self.anim_dir = 1
        self.canvas.itemconfig(self.anim_item, image=self.anim_frames[self.anim_idx])
        self.root.after(120, self._animate)

    def on_enable(self, e):
        if self.ex: self.ex.lock_enable(); self.ex.set_windowed(True); self.ex.set_chroma_key(True); self.on_click(96)

    def on_menu(self, e):
        if self.ex: self.ex.open_menu()

    def on_tickle(self, e):
        if self.ex: threading.Thread(target=self.ex.tickle_seaman, daemon=True).start()

    def on_spin(self, e):
        if self.ex: threading.Thread(target=self.ex.spin_seaman, daemon=True).start()

    def on_exit(self, e):
        if self.session: self.session.detach()
        self.root.destroy(); sys.exit(0)

    def on_ds(self, e): self.dsx, self.dsy = e.x_root, e.y_root
    def on_dm(self, e):
        dx, dy = e.x_root - self.dsx, e.y_root - self.dsy
        self.game_x += dx; self.game_y += dy; self.root.geometry(f"+{self.game_x}+{self.game_y}")
        user32.SetWindowPos(self.game_hwnd, None, self.game_x, self.game_y, 0, 0, 0x05)
        self.dsx, self.dsy = e.x_root, e.y_root

    def on_message(self, message, data):
        if message['type'] == 'send':
            p = message['payload']
            if p.get('type') == 'speech' and data:
                try:
                    text = data.decode('shift-jis', errors='replace')
                    print(f"🗣️ Seaman: {text}")
                    def trans():
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            eng = loop.run_until_complete(self.translator.translate(text, src='ja', dest='en')).text
                            print(f"💬 English: {eng}")
                            self.ex.inject_balloon_text(eng, p['p2'], p['p3'])
                        except: pass
                    threading.Thread(target=trans, daemon=True).start()
                except: pass

    def attach_frida(self):
        try:
            self.session = frida.attach(_PROCESS_NAME)
            js = FRIDA_SCRIPT.replace("'Seaman_1_2_57.exe'", f"'{_PROCESS_NAME}'")
            self.script = self.session.create_script(js)
            self.script.on('message', self.on_message)
            self.script.load(); self.ex = self.script.exports_sync
            print("[+] Frida attached with Translation")
        except: pass

    def run(self): self.root.mainloop()

if __name__ == '__main__': MenuOverlay().run()
