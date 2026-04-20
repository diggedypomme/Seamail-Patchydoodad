"""
Seaman Bridge v8.1 - Fixed UI with Semantic Labels
Receives 736-byte packets: 400 (param_4) + 336 (instance)
"""

import socket
import struct
import tkinter as tk
from tkinter import ttk
from threading import Thread
import time

UDP_PORT = 8888
WINDOW_W = 1200
WINDOW_H = 800

# Semantic field mappings (what we KNOW these values mean)
POSITION_FIELDS = [
    ("Location X", 0, "param", "%.2f"),
    ("Location Y", 1, "param", "%.2f"),
    ("Location Z", 2, "param", "%.2f"),
]

MOVEMENT_FIELDS = [
    ("Velocity X", 6, "param", "%.2f"),
    ("Velocity Y", 7, "param", "%.2f"),
    ("Velocity Z", 8, "param", "%.2f"),
    ("Pitch", 26, "param", "%.1f°"),
    ("Yaw", 27, "param", "%.1f°"),
]

STATE_FIELDS = [
    ("State Machine", 0, "instance", "%d"),
    ("Sub-State", 1, "instance", "%d"),
    ("Animation ID", 67, "instance", "%d"),
    ("Anim Counter", 68, "instance", "%d"),
]

DESTINATION_FIELDS = [
    ("Target X", 15, "instance_float", "%.2f"),
    ("Target Y", 16, "instance_float", "%.2f"),
    ("Target Z", 17, "instance_float", "%.2f"),
]

# Known param_4 field names
PARAM4_NAMES = {
    0: "Location X", 1: "Location Y", 2: "Location Z",
    6: "Velocity X", 7: "Velocity Y", 8: "Velocity Z",
    26: "Pitch", 27: "Yaw",
}

# Known instance field names
INSTANCE_NAMES = {
    0: "State Machine", 1: "Sub-State",
    15: "Target X", 16: "Target Y", 17: "Target Z",
    67: "Animation ID", 68: "Anim Counter",
}

# Instance fields that are actually floats (stored as DWORD)
INSTANCE_FLOAT_FIELDS = {15, 16, 17}  # Target X/Y/Z

class SeamanBridge81:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Seaman Bridge v8.1 - Semantic Labels")
        self.root.configure(bg="#0a0a0a")
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}")

        # Data storage
        self.param4 = [0.0] * 100
        self.instance = [0] * 84
        self.packet_count = 0
        self.last_update = 0

        # Previous values for color change detection
        self.param4_prev = [0.0] * 100
        self.instance_prev = [0] * 84
        self.change_times = [[0.0] * 100, [0.0] * 84]

        # Current view mode
        self.view_mode = tk.StringVar(value="position")

        # Raw instance display format
        self.instance_format = tk.StringVar(value="auto")

        # Raw param_4 display format
        self.param4_format = tk.StringVar(value="float")

        self.create_ui()

        # Start UDP receiver thread
        self.running = True
        self.udp_thread = Thread(target=self.udp_receiver, daemon=True)
        self.udp_thread.start()

        # Start UI update loop
        self.update_ui()

    def create_ui(self):
        # Top status bar
        status_frame = tk.Frame(self.root, bg="#1a1a1a", height=40)
        status_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        status_frame.pack_propagate(False)

        self.status_label = tk.Label(status_frame, text="Waiting for data...",
                                     bg="#1a1a1a", fg="#00ff00", font=("Consolas", 12, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=10)

        # View mode buttons
        btn_frame = tk.Frame(self.root, bg="#0a0a0a")
        btn_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        modes = [
            ("Position & Movement", "position"),
            ("State & Animation", "state"),
            ("All Fields", "all"),
            ("Raw param_4", "raw_param4"),
            ("Raw Instance", "raw_instance"),
        ]

        for label, mode in modes:
            btn = tk.Button(btn_frame, text=label,
                          command=lambda m=mode: self.view_mode.set(m),
                          bg="#2a2a2a", fg="#ffffff", font=("Consolas", 10),
                          activebackground="#3a3a3a", relief=tk.RAISED, bd=2)
            btn.pack(side=tk.LEFT, padx=5)

        # 3D Preview Canvas (shown/hidden based on view mode)
        self.preview_frame = tk.Frame(self.root, bg="#1a1a1a", relief="ridge", bd=2)

        tk.Label(self.preview_frame, text="POSITION PREVIEW", bg="#1a1a1a", fg="#ffffff",
                font=("Consolas", 11, "bold")).pack(pady=5)

        self.canvas = tk.Canvas(self.preview_frame, bg="#000000", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Data display area
        self.data_frame = tk.Frame(self.root, bg="#0a0a0a")

        self.field_labels = {}
        self.create_data_display()

    def create_data_display(self):
        # Clear existing widgets
        for widget in self.data_frame.winfo_children():
            widget.destroy()

        # Clear field labels dict (old references are invalid)
        self.field_labels = {}

        # Get view mode
        mode = self.view_mode.get()

        # IMPORTANT: Unpack both frames first to reset order
        self.preview_frame.pack_forget()
        self.data_frame.pack_forget()

        # Show/hide preview based on mode
        if mode in ["raw_param4", "raw_instance"]:
            # Raw views use full window - hide preview, show only data
            self.data_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        else:
            # Normal views: preview on top, data below
            self.preview_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
            self.data_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=5, pady=5)

        # Container with proper layout
        container = tk.Frame(self.data_frame, bg="#1a1a1a", relief="ridge", bd=2)
        container.pack(fill=tk.BOTH, expand=True)

        # Create columns based on view mode
        if mode == "position":
            self.create_column(container, "LOCATION", POSITION_FIELDS, 0)
            self.create_column(container, "MOVEMENT", MOVEMENT_FIELDS, 1)
        elif mode == "state":
            self.create_column(container, "STATE MACHINE", STATE_FIELDS, 0)
            self.create_column(container, "DESTINATION", DESTINATION_FIELDS, 1)
        elif mode == "all":
            self.create_column(container, "LOCATION", POSITION_FIELDS, 0)
            self.create_column(container, "MOVEMENT", MOVEMENT_FIELDS, 1)
            self.create_column(container, "STATE", STATE_FIELDS, 2)
            self.create_column(container, "DESTINATION", DESTINATION_FIELDS, 3)
        elif mode == "raw_param4":
            self.create_raw_param4_grid(container)
        elif mode == "raw_instance":
            self.create_raw_instance_grid(container)

    def create_column(self, parent, title, fields, col):
        frame = tk.Frame(parent, bg="#1a1a1a")
        frame.grid(row=0, column=col, sticky="nsew", padx=10, pady=10)
        parent.grid_columnconfigure(col, weight=1)

        tk.Label(frame, text=title, bg="#2a2a2a", fg="#ffffff",
                font=("Consolas", 10, "bold"), anchor="w", padx=10, pady=5).pack(fill=tk.X)

        for label, idx, source, fmt in fields:
            row = tk.Frame(frame, bg="#1a1a1a")
            row.pack(fill=tk.X, padx=10, pady=3)

            tk.Label(row, text=label + ":", bg="#1a1a1a", fg="#888888",
                    font=("Consolas", 9), anchor="w", width=15).pack(side=tk.LEFT)

            value_label = tk.Label(row, text="--", bg="#1a1a1a", fg="#00ff00",
                                  font=("Consolas", 9, "bold"), anchor="e", width=12)
            value_label.pack(side=tk.RIGHT)

            key = f"{source}_{idx}"
            self.field_labels[key] = (value_label, source, idx, fmt)

    def create_raw_param4_grid(self, parent):
        # Create grid for all 100 param_4 floats - FULL WINDOW
        frame = tk.Frame(parent, bg="#1a1a1a")
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Header with format toggle buttons
        header_frame = tk.Frame(frame, bg="#2a2a2a")
        header_frame.pack(fill=tk.X)

        tk.Label(header_frame, text="param_4 (100 floats) - Color: Green=UP, Red=DOWN",
                bg="#2a2a2a", fg="#00ff00", font=("Consolas", 11, "bold"),
                anchor="w", padx=10, pady=8).pack(side=tk.LEFT)

        # Format toggle buttons
        tk.Label(header_frame, text="Format:", bg="#2a2a2a", fg="#ffffff",
                font=("Consolas", 9)).pack(side=tk.LEFT, padx=(20, 5))

        formats = [
            ("Float", "float", "Just float value"),
            ("Float+Hex", "float_hex", "Float + hex bits"),
            ("Float+Int", "float_int", "Float + int cast"),
            ("Hex", "hex", "As hex 32-bit"),
            ("Int", "int", "As 32-bit integer"),
        ]

        for label, mode, tooltip in formats:
            btn = tk.Button(header_frame, text=label,
                          command=lambda m=mode: self.param4_format.set(m),
                          bg="#3a3a3a", fg="#ffffff", font=("Consolas", 8),
                          activebackground="#4a4a4a", relief=tk.RAISED, bd=1,
                          padx=5, pady=2)
            btn.pack(side=tk.LEFT, padx=2)

        grid_frame = tk.Frame(frame, bg="#1a1a1a")
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.p4_labels = []
        # 4 columns, 25 rows each
        for i in range(100):
            col_num = i // 25
            row_num = i % 25

            # Get semantic name if known
            name = PARAM4_NAMES.get(i, "")
            label_text = f"f{i}: {name}" if name else f"f{i}"

            # Create row frame
            row_frame = tk.Frame(grid_frame, bg="#1a1a1a")
            row_frame.grid(row=row_num, column=col_num, sticky="ew", padx=5, pady=1)
            grid_frame.grid_columnconfigure(col_num, weight=1)

            # Label (index + name)
            tk.Label(row_frame, text=label_text, fg="#888", bg="#1a1a1a",
                    font=("Consolas", 9), width=18, anchor="w").pack(side=tk.LEFT)

            # Value (wider to fit float+hex format)
            val_lbl = tk.Label(row_frame, text="0.00", fg="#555", bg="#1a1a1a",
                              font=("Consolas", 9, "bold"), width=25, anchor="e")
            val_lbl.pack(side=tk.RIGHT)
            self.p4_labels.append(val_lbl)

    def create_raw_instance_grid(self, parent):
        # Create grid for all 84 instance DWORDs - FULL WINDOW
        frame = tk.Frame(parent, bg="#1a1a1a")
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Header with format toggle buttons
        header_frame = tk.Frame(frame, bg="#2a2a2a")
        header_frame.pack(fill=tk.X)

        tk.Label(header_frame, text="Instance Fields (84 DWORDs) - Color: Yellow=CHANGED",
                bg="#2a2a2a", fg="#ff00ff", font=("Consolas", 11, "bold"),
                anchor="w", padx=10, pady=8).pack(side=tk.LEFT)

        # Format toggle buttons
        tk.Label(header_frame, text="Format:", bg="#2a2a2a", fg="#ffffff",
                font=("Consolas", 9)).pack(side=tk.LEFT, padx=(20, 5))

        formats = [
            ("Auto", "auto", "Known floats only"),
            ("All Float", "all_float", "Decode all as floats"),
            ("Int+Float", "int_float", "Int and float, no hex"),
            ("Int+Hex", "int_hex", "No float decode"),
        ]

        for label, mode, tooltip in formats:
            btn = tk.Button(header_frame, text=label,
                          command=lambda m=mode: self.instance_format.set(m),
                          bg="#3a3a3a", fg="#ffffff", font=("Consolas", 8),
                          activebackground="#4a4a4a", relief=tk.RAISED, bd=1,
                          padx=5, pady=2)
            btn.pack(side=tk.LEFT, padx=2)

        grid_frame = tk.Frame(frame, bg="#1a1a1a")
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.inst_labels = []
        # 3 columns, 28 rows each
        for i in range(84):
            col_num = i // 28
            row_num = i % 28
            offset = 0xa4 + i*4

            # Get semantic name if known
            name = INSTANCE_NAMES.get(i, "")
            label_text = f"[{offset:03x}] i{i}: {name}" if name else f"[{offset:03x}] i{i}"

            # Create row frame
            row_frame = tk.Frame(grid_frame, bg="#1a1a1a")
            row_frame.grid(row=row_num, column=col_num, sticky="ew", padx=5, pady=1)
            grid_frame.grid_columnconfigure(col_num, weight=1)

            # Label (offset + index + name)
            tk.Label(row_frame, text=label_text, fg="#888", bg="#1a1a1a",
                    font=("Consolas", 9), width=25, anchor="w").pack(side=tk.LEFT)

            # Value (wider to fit int + hex + float)
            val_lbl = tk.Label(row_frame, text="0 (0x00000000)", fg="#555", bg="#1a1a1a",
                              font=("Consolas", 9, "bold"), width=35, anchor="e")
            val_lbl.pack(side=tk.RIGHT)
            self.inst_labels.append(val_lbl)

    def udp_receiver(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", UDP_PORT))
        sock.settimeout(1.0)

        print(f"[UDP] Listening on port {UDP_PORT}")

        while self.running:
            try:
                data, addr = sock.recvfrom(2048)
                if len(data) != 736:
                    continue

                self.param4 = list(struct.unpack('<100f', data[0:400]))
                self.instance = list(struct.unpack('<84I', data[400:736]))
                self.packet_count += 1
                self.last_update = time.time()

            except socket.timeout:
                continue
            except Exception as e:
                print(f"[UDP] Error: {e}")

    def update_ui(self):
        # Check if view mode changed
        if hasattr(self, '_last_view_mode'):
            if self._last_view_mode != self.view_mode.get():
                self.create_data_display()
        self._last_view_mode = self.view_mode.get()

        if self.last_update > 0:
            now = time.time()

            # Update all field labels with color changes
            for key, (label, source, idx, fmt) in self.field_labels.items():
                try:
                    if source == "param":
                        value = self.param4[idx]
                        prev_value = self.param4_prev[idx]
                        delta = value - prev_value

                        # Color based on change
                        if abs(delta) > 0.01:
                            self.change_times[0][idx] = now
                            color = "#00ff00" if delta > 0 else "#ff0000"
                        elif now - self.change_times[0][idx] > 2.0:
                            color = "#00ff00"  # Default green
                        else:
                            color = label.cget("fg")  # Keep current color

                        label.config(text=fmt % value, fg=color)
                        self.param4_prev[idx] = value

                    elif source == "instance":
                        value = self.instance[idx]
                        prev_value = self.instance_prev[idx]

                        # Color based on change
                        if value != prev_value:
                            self.change_times[1][idx] = now
                            color = "#ffff00"  # Yellow for changes
                        elif now - self.change_times[1][idx] > 2.0:
                            color = "#00ff00"  # Default green
                        else:
                            color = label.cget("fg")  # Keep current color

                        label.config(text=fmt % value, fg=color)
                        self.instance_prev[idx] = value

                    elif source == "instance_float":
                        # Convert DWORD to float
                        value = struct.unpack('<f', struct.pack('<I', self.instance[idx]))[0]
                        prev_dword = self.instance_prev[idx]
                        prev_value = struct.unpack('<f', struct.pack('<I', prev_dword))[0]
                        delta = value - prev_value

                        # Color based on change
                        if abs(delta) > 0.01:
                            self.change_times[1][idx] = now
                            color = "#00ff00" if delta > 0 else "#ff0000"
                        elif now - self.change_times[1][idx] > 2.0:
                            color = "#00ff00"  # Default green
                        else:
                            color = label.cget("fg")  # Keep current color

                        label.config(text=fmt % value, fg=color)
                        self.instance_prev[idx] = self.instance[idx]

                except tk.TclError:
                    # Label was destroyed (view mode changed), skip it
                    pass

            # Update raw param_4 grid with color changes
            if self.view_mode.get() == "raw_param4" and hasattr(self, 'p4_labels'):
                format_mode = self.param4_format.get()

                for i in range(100):
                    val = self.param4[i]
                    delta = val - self.param4_prev[i]

                    # Format based on selected mode
                    if format_mode == "float_hex":
                        # Float + hex representation of bits
                        int_bits = struct.unpack('<I', struct.pack('<f', val))[0]
                        text = f"{val:.2f} (0x{int_bits:08x})"
                    elif format_mode == "float_int":
                        # Float + integer cast
                        text = f"{val:.2f} = {int(val)}"
                    elif format_mode == "hex":
                        # Just hex of the float bits
                        int_bits = struct.unpack('<I', struct.pack('<f', val))[0]
                        text = f"0x{int_bits:08x}"
                    elif format_mode == "int":
                        # Just integer cast
                        int_bits = struct.unpack('<I', struct.pack('<f', val))[0]
                        text = f"{int_bits}"
                    else:  # float (default)
                        # Just the float value
                        text = f"{val:.2f}"

                    if abs(delta) > 0.01:
                        self.change_times[0][i] = now
                        color = "#00ff00" if delta > 0 else "#ff0000"
                        self.p4_labels[i].config(text=text, fg=color)
                    elif now - self.change_times[0][i] > 2.0:
                        self.p4_labels[i].config(text=text, fg="#555")
                    else:
                        self.p4_labels[i].config(text=text)

                    self.param4_prev[i] = val

            # Update raw instance grid with color changes
            if self.view_mode.get() == "raw_instance" and hasattr(self, 'inst_labels'):
                format_mode = self.instance_format.get()

                for i in range(84):
                    val = self.instance[i]

                    # Format based on selected mode
                    if format_mode == "all_float":
                        # Decode ALL fields as floats
                        float_val = struct.unpack('<f', struct.pack('<I', val))[0]
                        text = f"{val} (0x{val:08x}) = {float_val:.2f}"
                    elif format_mode == "int_float":
                        # Int + float, no hex
                        float_val = struct.unpack('<f', struct.pack('<I', val))[0]
                        text = f"{val} = {float_val:.2f}"
                    elif format_mode == "int_hex":
                        # Just int + hex, no float
                        text = f"{val} (0x{val:08x})"
                    else:  # auto
                        # Only decode known float fields
                        if i in INSTANCE_FLOAT_FIELDS:
                            float_val = struct.unpack('<f', struct.pack('<I', val))[0]
                            text = f"{val} (0x{val:08x}) = {float_val:.2f}"
                        else:
                            text = f"{val} (0x{val:08x})"

                    if val != self.instance_prev[i]:
                        self.change_times[1][i] = now
                        self.inst_labels[i].config(text=text, fg="#ffff00")
                    elif now - self.change_times[1][i] > 2.0:
                        self.inst_labels[i].config(text=text, fg="#555")
                    else:
                        self.inst_labels[i].config(text=text)

                    self.instance_prev[i] = val

            # Update 3D preview
            self.draw_preview()

            # Update status
            state = self.instance[0]
            anim = self.instance[67]
            self.status_label.config(
                text=f"RECEIVING | Packets: {self.packet_count} | State: {state} | Anim: {anim}",
                fg="#00ff00")
        else:
            age = time.time() - (self.last_update if self.last_update > 0 else time.time())
            if self.packet_count == 0 and age > 5:
                self.status_label.config(
                    text=f"NO DATA for {age:.0f}s - Check if tracker is running",
                    fg="#ff0000")

        self.root.after(50, self.update_ui)

    def draw_preview(self):
        # Clear canvas
        self.canvas.delete("all")

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 1 or h <= 1:
            return

        # Tank boundaries (SIDE VIEW: X/Y plane)
        tank_x_range = 150  # -100 to 100
        tank_y_range = 100  # -50 to 50

        # Scale to fit canvas
        scale_x = (w - 40) / tank_x_range
        scale_y = (h - 40) / tank_y_range
        scale = min(scale_x, scale_y)  # Use same scale for both axes

        # Center point
        cx = w / 2
        cy = h / 2

        # Draw axes
        self.canvas.create_line(20, cy, w-20, cy, fill="#333333", width=1)  # X axis
        self.canvas.create_line(cx, 20, cx, h-20, fill="#333333", width=1)  # Y axis

        # Draw tank boundary
        tank_w = tank_x_range * scale
        tank_h = tank_y_range * scale
        x1 = cx - tank_w/2
        y1 = cy - tank_h/2
        x2 = cx + tank_w/2
        y2 = cy + tank_h/2
        self.canvas.create_rectangle(x1, y1, x2, y2, outline="#444444", width=2)

        # Get position (SIDE VIEW uses X and Y)
        pos_x = self.param4[0]
        pos_y = self.param4[1]
        pos_z = self.param4[2]  # Z used for depth scaling, not displayed

        # Convert to canvas coords
        canvas_x = cx + (pos_x * scale)
        canvas_y = cy - (pos_y * scale)  # Flip Y for canvas

        # Depth scaling (like bridge7)
        depth_scale = max(0.2, 1.0 - pos_z/400)

        # Draw velocity vector (red) - uses X/Y for side view
        import math
        vel_x = self.param4[6]
        vel_y = self.param4[7]  # Y, not Z, for side view

        # Calculate body angle from velocity direction
        if abs(vel_x) > 0.01 or abs(vel_y) > 0.01:
            body_angle = math.atan2(-vel_y, vel_x)  # Body oriented in direction of movement
            vel_end_x = canvas_x + vel_x * 50 * depth_scale
            vel_end_y = canvas_y - vel_y * 50 * depth_scale
            self.canvas.create_line(canvas_x, canvas_y, vel_end_x, vel_end_y,
                                   fill="#ff0000", width=3, arrow=tk.LAST)
        else:
            body_angle = 0  # Default if not moving

        # Draw Seaman body (circle)
        br = 15 * depth_scale  # Body radius
        self.canvas.create_oval(canvas_x-br, canvas_y-br, canvas_x+br, canvas_y+br,
                               outline="#00ffff", width=3)

        # Head rotation (yaw/pitch) is RELATIVE to body orientation
        yaw_rad = math.radians(self.param4[27])
        pitch_rad = math.radians(self.param4[26])

        # Combine body angle + head rotation (yaw negated, pitch NOT negated)
        total_angle_x = body_angle - yaw_rad
        total_angle_y = body_angle + pitch_rad

        # Calculate face position (body orientation + head rotation)
        fx = canvas_x + math.cos(total_angle_x) * br * 0.7
        fy = canvas_y - math.sin(total_angle_y) * br * 0.7

        # Draw face (smaller circle)
        fr = 6 * depth_scale  # Face radius
        self.canvas.create_oval(fx-fr, fy-fr, fx+fr, fy+fr,
                               fill="#ff00ff", outline="white")

        # Draw gaze arrow (from body center through face + extended)
        # This combines fish body rotation + head rotation
        gaze_end_x = fx + math.cos(total_angle_x) * 60 * depth_scale
        gaze_end_y = fy - math.sin(total_angle_y) * 60 * depth_scale
        self.canvas.create_line(canvas_x, canvas_y, gaze_end_x, gaze_end_y,
                               fill="#00ff00", width=2, arrow=tk.LAST)

        # Draw destination (yellow dashed circle)
        dest_x_float = struct.unpack('<f', struct.pack('<I', self.instance[15]))[0]
        dest_y_float = struct.unpack('<f', struct.pack('<I', self.instance[16]))[0]
        dest_canvas_x = cx + (dest_x_float * scale)
        dest_canvas_y = cy - (dest_y_float * scale)
        dr = 10
        self.canvas.create_oval(dest_canvas_x-dr, dest_canvas_y-dr,
                               dest_canvas_x+dr, dest_canvas_y+dr,
                               outline="#ffff00", width=2, dash=(5, 3))

        # Draw labels
        self.canvas.create_text(w/2, 15, text="SIDE VIEW (X/Y plane)",
                               fill="#ffffff", font=("Consolas", 10, "bold"))
        self.canvas.create_text(w-10, cy, text="X+", anchor="e", fill="#888888", font=("Consolas", 8))
        self.canvas.create_text(cx, 10, text="Y+", fill="#888888", font=("Consolas", 8))

    def run(self):
        self.root.mainloop()
        self.running = False

if __name__ == "__main__":
    print("=" * 60)
    print("Seaman Bridge v8.1 - Semantic Labels + 3D Preview")
    print("=" * 60)
    print()
    print("UDP Port: 8888")
    print()

    bridge = SeamanBridge81()
    bridge.run()
