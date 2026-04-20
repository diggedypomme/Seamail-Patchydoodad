"""
Seaman Position Tracker for Windows 11 (Frida version)
Replaces xp_debug_tracker_v8.1.exe for Win11 systems

Captures:
- param_4 structure (100 floats) at instance - 0x250
- instance data (84 DWORDs) starting from instance base
- Sends 736-byte UDP packets to localhost:8888
- Compatible with position_tracker_2 server

Usage:
    python win11_tracker.py                    # Send to localhost:8888
    python win11_tracker.py --ip=192.168.0.6   # Send to custom IP
"""

import frida
import sys
import socket
import struct
import time
import argparse
import threading
from queue import Queue

# Parse args
parser = argparse.ArgumentParser()
parser.add_argument('--ip',      default='127.0.0.1',  help='Target IP for UDP packets')
parser.add_argument('--port',    type=int, default=8888, help='Target UDP port')
parser.add_argument('--process', default='Seaman.exe',  help='Process name to attach to')
args = parser.parse_args()

UDP_IP = args.ip
UDP_PORT = args.port

# Create UDP socket (non-blocking)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setblocking(False)

# Packet queue for async sending
packet_queue = Queue(maxsize=100)
packet_count = 0

def udp_sender_thread():
    """Dedicated thread for sending UDP packets - doesn't block Frida message processing"""
    global packet_count
    while True:
        try:
            data = packet_queue.get()
            if data is None:  # Shutdown signal
                break

            sock.sendto(data, (UDP_IP, UDP_PORT))
            packet_count += 1

            if packet_count == 1:
                print(f"[UDP] Sending to {UDP_IP}:{UDP_PORT}")
                print(f"[UDP] *** FIRST PACKET sent (736 bytes) ***")
            elif packet_count % 50 == 0:
                print(f"[UDP] {packet_count} packets sent")

        except Exception as e:
            print(f"[UDP ERROR] {e}")

# Start sender thread
sender = threading.Thread(target=udp_sender_thread, daemon=True)
sender.start()

def on_message(message, data):
    if message['type'] == 'send':
        payload = message['payload']

        if payload.get('type') == 'instance_found':
            print(f"[FRIDA] Instance captured at 0x{payload['address']:x}")
            print(f"[FRIDA]   State={payload['state']}, AnimID={payload['anim_id']}")

        elif payload.get('type') == 'data':
            # Queue packet for async sending (doesn't block Frida)
            if data and len(data) == 736:
                try:
                    packet_queue.put_nowait(data)  # Non-blocking queue add
                except:
                    print(f"[WARN] Packet queue full, dropping packet")
            else:
                print(f"[ERROR] Unexpected data size: {len(data) if data else 0} bytes")

    elif message['type'] == 'error':
        print(f"[FRIDA ERROR] {message['stack']}")


# Frida script — TARGET_PROCESS replaced at runtime
js_code = """
// Track instance pointer
var instance_ptr = null;
var state_handler_addr = null;

// Find process base
var target_name = 'TARGET_PROCESS';
var seaman_base = null;
Process.enumerateModules().forEach(function(mod) {
    if (mod.name.toLowerCase() === target_name) {
        seaman_base = mod.base;
    }
});

if (!seaman_base) {
    send({type: 'error', msg: target_name + ' not found'});
    throw new Error(target_name + ' not found');
}

// State handler at base + 0x7E60 (CHigyoBrain::Action)
state_handler_addr = seaman_base.add(0x7E60);

send({type: 'info', msg: 'Hooking state handler at 0x' + state_handler_addr.toString(16)});

// Hook to capture instance pointer
Interceptor.attach(state_handler_addr, {
    onEnter: function(args) {
        // ECX contains 'this' pointer (instance)
        var ecx = this.context.ecx;

        if (!instance_ptr || !instance_ptr.equals(ecx)) {
            instance_ptr = ecx;

            // Read state and anim_id for verification
            var state = instance_ptr.add(0xa4).readU32();
            var anim_id = instance_ptr.add(0x1b0).readU32();

            send({
                type: 'instance_found',
                address: instance_ptr.toInt32(),
                state: state,
                anim_id: anim_id
            });
        }
    }
});

// Send data every 50ms (20Hz) - matches XP tracker
setInterval(function() {
    if (!instance_ptr) return;

    try {
        // Read param_4 (100 floats = 400 bytes) at instance - 0x250
        var param4_addr = instance_ptr.sub(0x250);
        var param4_bytes = param4_addr.readByteArray(400);

        // Read instance data (84 DWORDs = 336 bytes) starting at instance + 0xa4
        // This matches the XP tracker exactly:
        //   instanceBuffer[0]  = instance+0xa4  (state)
        //   instanceBuffer[1]  = instance+0xa8  (sub_state)
        //   instanceBuffer[15] = instance+0xe0  (destX as float-in-DWORD)
        //   instanceBuffer[67] = instance+0x1b0 (anim_id)
        //   etc.
        var instance_addr = instance_ptr.add(0xa4);
        var instance_bytes = instance_addr.readByteArray(336);

        // Combine into 736-byte packet (same as XP C++ version)
        var combined = new Uint8Array(736);
        combined.set(new Uint8Array(param4_bytes), 0);      // bytes 0-399
        combined.set(new Uint8Array(instance_bytes), 400);  // bytes 400-735

        // Send binary data
        send({type: 'data'}, combined.buffer);

    } catch (e) {
        send({type: 'error', msg: 'Read error: ' + e.message});
    }

}, 50); // 20Hz update rate (matches XP tracker)
""".replace("TARGET_PROCESS", args.process.lower())

print("=" * 60)
print("Seaman Win11 Position Tracker (Frida)")
print(f"  Target:  {args.process}")
print(f"  UDP out: {UDP_IP}:{UDP_PORT}")
print("=" * 60)
print()

# Attach to target process
try:
    session = frida.attach(args.process)
    print(f"[FRIDA] Attached to {args.process}")
except frida.ProcessNotFoundError:
    print(f"[ERROR] {args.process} is not running!")
    sys.exit(1)

script = session.create_script(js_code)
script.on('message', on_message)
script.load()

print("[FRIDA] Script loaded, monitoring instance...")
print()

try:
    sys.stdin.read()
except KeyboardInterrupt:
    print("\n[STOPPED]")
    sock.close()
