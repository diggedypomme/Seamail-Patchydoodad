"""
Seaman Bridge v8 - Clean Named Fields Layout
Receives 736-byte packets from v7.2: 400 (param_4) + 336 (instance)
"""

import socket
import struct
import tkinter as tk
from threading import Thread
import time

UDP_PORT = 8888
WINDOW_W = 1400
WINDOW_H = 900

class SeamanBridgeV8:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Seaman Bridge v8 - Named Fields")
        self.root.configure(bg="#0a0a0a")
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}")

        # Data storage
        self.param4 = [0.0] * 100
        self.instance = [0] * 84
        self.packet_count = 0
        self.last_update = 0

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

        # Main content area - 3 columns
        content = tk.Frame(self.root, bg="#0a0a0a")
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left column: Position & Movement
        left_col = tk.Frame(content, bg="#1a1a1a", relief="ridge", bd=2)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.add_section_header(left_col, "POSITION & MOVEMENT")
        self.pos_labels = {}
        pos_fields = [
            ("Position X", "pos_x", "#00ff00"),
            ("Position Y", "pos_y", "#00ff00"),
            ("Position Z", "pos_z", "#00ff00"),
            ("Direction X", "dir_x", "#ff8800"),
            ("Direction Y", "dir_y", "#ff8800"),
            ("Direction Z", "dir_z", "#ff8800"),
            ("Pitch", "pitch", "#8888ff"),
            ("Yaw", "yaw", "#8888ff"),
        ]
        for label, key, color in pos_fields:
            self.add_field_row(left_col, label, key, color, self.pos_labels)

        # Middle column: State & Animation
        mid_col = tk.Frame(content, bg="#1a1a1a", relief="ridge", bd=2)
        mid_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.add_section_header(mid_col, "STATE & ANIMATION")
        self.state_labels = {}
        state_fields = [
            ("State", "state", "#ff00ff"),
            ("Sub-State", "sub_state", "#ff00ff"),
            ("Animation ID", "anim_id", "#00ffff"),
            ("Anim Counter", "anim_count", "#00ffff"),
            ("Destination X", "dest_x", "#ffff00"),
            ("Destination Y", "dest_y", "#ffff00"),
            ("Destination Z", "dest_z", "#ffff00"),
        ]
        for label, key, color in state_fields:
            self.add_field_row(mid_col, label, key, color, self.state_labels)

        # Right column: Debug & Raw
        right_col = tk.Frame(content, bg="#1a1a1a", relief="ridge", bd=2)
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.add_section_header(right_col, "DEBUG INFO")
        self.debug_labels = {}
        debug_fields = [
            ("Packets Received", "packets", "#00ff00"),
            ("Last Update", "last_update", "#00ff00"),
            ("Instance Addr", "instance_addr", "#ffaa00"),
        ]
        for label, key, color in debug_fields:
            self.add_field_row(right_col, label, key, color, self.debug_labels)

        # Bottom: Raw data display (scrollable)
        bottom_frame = tk.Frame(self.root, bg="#1a1a1a", relief="ridge", bd=2)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=5, pady=5)

        tk.Label(bottom_frame, text="RAW MEMORY VIEW",
                bg="#1a1a1a", fg="#ffffff", font=("Consolas", 10, "bold")).pack(pady=5)

        # Scrollable text area
        scroll_frame = tk.Frame(bottom_frame, bg="#0a0a0a")
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = tk.Scrollbar(scroll_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.raw_text = tk.Text(scroll_frame, bg="#0a0a0a", fg="#00ff00",
                               font=("Consolas", 9), height=10,
                               yscrollcommand=scrollbar.set)
        self.raw_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.raw_text.yview)

    def add_section_header(self, parent, text):
        header = tk.Label(parent, text=text, bg="#2a2a2a", fg="#ffffff",
                         font=("Consolas", 11, "bold"), anchor="w", padx=10, pady=5)
        header.pack(fill=tk.X, pady=(0, 5))

    def add_field_row(self, parent, label, key, color, label_dict):
        row = tk.Frame(parent, bg="#1a1a1a")
        row.pack(fill=tk.X, padx=10, pady=2)

        tk.Label(row, text=label + ":", bg="#1a1a1a", fg="#888888",
                font=("Consolas", 10), anchor="w", width=15).pack(side=tk.LEFT)

        value_label = tk.Label(row, text="--", bg="#1a1a1a", fg=color,
                              font=("Consolas", 10, "bold"), anchor="e", width=20)
        value_label.pack(side=tk.RIGHT)
        label_dict[key] = value_label

    def udp_receiver(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", UDP_PORT))
        sock.settimeout(1.0)

        print(f"[UDP] Listening on port {UDP_PORT}")
        print(f"[UDP] Expecting 736-byte packets (400 + 336)")

        while self.running:
            try:
                data, addr = sock.recvfrom(2048)
                if len(data) != 736:
                    print(f"[UDP] WARNING: Received {len(data)} bytes (expected 736)")
                    continue

                # Parse packet
                self.param4 = list(struct.unpack('<100f', data[0:400]))
                self.instance = list(struct.unpack('<84I', data[400:736]))
                self.packet_count += 1
                self.last_update = time.time()

                if self.packet_count % 20 == 0:  # Print every 20th packet
                    print(f"[UDP] Packet #{self.packet_count} from {addr[0]}:{addr[1]}")

            except socket.timeout:
                continue
            except Exception as e:
                print(f"[UDP] Error: {e}")

    def update_ui(self):
        if self.last_update > 0:
            # Position & Movement (from param_4)
            self.pos_labels["pos_x"].config(text=f"{self.param4[0]:.2f}")
            self.pos_labels["pos_y"].config(text=f"{self.param4[1]:.2f}")
            self.pos_labels["pos_z"].config(text=f"{self.param4[2]:.2f}")
            self.pos_labels["dir_x"].config(text=f"{self.param4[6]:.2f}")
            self.pos_labels["dir_y"].config(text=f"{self.param4[7]:.2f}")
            self.pos_labels["dir_z"].config(text=f"{self.param4[8]:.2f}")
            self.pos_labels["pitch"].config(text=f"{self.param4[26]:.1f}°")
            self.pos_labels["yaw"].config(text=f"{self.param4[27]:.1f}°")

            # State & Animation (from instance)
            state = self.instance[0]  # instance+0xa4
            sub_state = self.instance[1]  # instance+0xa8
            anim_id = self.instance[67]  # instance+0x1b0
            anim_count = self.instance[68]  # instance+0x1b4

            # Destination as floats
            dest_x = struct.unpack('<f', struct.pack('<I', self.instance[15]))[0]
            dest_y = struct.unpack('<f', struct.pack('<I', self.instance[16]))[0]
            dest_z = struct.unpack('<f', struct.pack('<I', self.instance[17]))[0]

            self.state_labels["state"].config(text=f"{state}")
            self.state_labels["sub_state"].config(text=f"{sub_state}")
            self.state_labels["anim_id"].config(text=f"{anim_id}")
            self.state_labels["anim_count"].config(text=f"{anim_count}")
            self.state_labels["dest_x"].config(text=f"{dest_x:.2f}")
            self.state_labels["dest_y"].config(text=f"{dest_y:.2f}")
            self.state_labels["dest_z"].config(text=f"{dest_z:.2f}")

            # Debug info
            age = time.time() - self.last_update
            self.debug_labels["packets"].config(text=f"{self.packet_count}")
            self.debug_labels["last_update"].config(text=f"{age:.1f}s ago")
            self.debug_labels["instance_addr"].config(text=f"0x{self.instance[0]:08X}")

            self.status_label.config(text=f"RECEIVING | Packets: {self.packet_count} | State: {state} | Anim: {anim_id}",
                                    fg="#00ff00")

            # Update raw memory view (first 20 values of each)
            self.raw_text.delete(1.0, tk.END)
            self.raw_text.insert(tk.END, "param_4 floats (first 20):\n", "header")
            for i in range(20):
                self.raw_text.insert(tk.END, f"[{i:2d}] {self.param4[i]:9.2f}  ", "data")
                if (i + 1) % 5 == 0:
                    self.raw_text.insert(tk.END, "\n")

            self.raw_text.insert(tk.END, "\n\nInstance DWORDs (first 20):\n", "header")
            for i in range(20):
                self.raw_text.insert(tk.END, f"[{i:2d}] 0x{self.instance[i]:08X}  ", "data")
                if (i + 1) % 4 == 0:
                    self.raw_text.insert(tk.END, "\n")

            self.raw_text.tag_config("header", foreground="#ffff00", font=("Consolas", 9, "bold"))
            self.raw_text.tag_config("data", foreground="#00ff00")
        else:
            # No data yet
            age_since_start = time.time() - (self.last_update if self.last_update > 0 else time.time())
            if self.packet_count == 0 and age_since_start > 5:
                self.status_label.config(
                    text=f"NO DATA for {age_since_start:.0f}s - Check if tracker is running with --network",
                    fg="#ff0000")

        # Schedule next update (50ms = 20Hz)
        self.root.after(50, self.update_ui)

    def run(self):
        self.root.mainloop()
        self.running = False

if __name__ == "__main__":
    print("=" * 60)
    print("Seaman Bridge v8 - Named Fields Layout")
    print("=" * 60)
    print()
    print("Expecting v7.2 tracker to send:")
    print("  - 736 bytes total")
    print("  - 400 bytes: param_4 (100 floats)")
    print("  - 336 bytes: instance (84 DWORDs)")
    print()
    print("UDP Port: 8888")
    print()

    bridge = SeamanBridgeV8()
    bridge.run()
