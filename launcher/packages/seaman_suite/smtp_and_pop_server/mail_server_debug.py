import socket
import threading
import os
import time
import datetime

# --- Configuration (DEBUG MODE) ---
SMTP_PORT = 2525  # Shifted from 25
POP3_PORT = 1100  # Shifted from 110
HOST = '0.0.0.0'

MAIL_IN_DIR = 'mail_in'
MAIL_OUT_DIR = 'mail_out'

# Create directories if they don't exist
for d in [MAIL_IN_DIR, MAIL_OUT_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

def get_timestamp():
    return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

def line_reader(conn):
    """Generator to yield lines from a socket with graceful reset handling."""
    buffer = b""
    while True:
        try:
            data = conn.recv(4096)
            if not data:
                if buffer:
                    yield buffer.decode('utf-8', errors='ignore')
                break
            buffer += data
            while b"\r\n" in buffer:
                line, buffer = buffer.split(b"\r\n", 1)
                yield line.decode('utf-8', errors='ignore').strip()
            if b"\n" in buffer and b"\r\n" not in buffer:
                line, buffer = buffer.split(b"\n", 1)
                yield line.decode('utf-8', errors='ignore').strip()
        except ConnectionResetError:
            print("[!] Connection was reset by the client (10054).")
            break
        except Exception as e:
            print(f"[!] Error in line_reader: {e}")
            break

# --- SMTP Server Logic ---
class SmtpServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def handle_client(self, conn, addr):
        print(f"[SMTP] Connection from {addr}")
        try:
            conn.sendall(b"220 Fake SMTP Server Ready (DEBUG)\r\n")
            mail_data = []
            in_data_mode = False

            for line in line_reader(conn):
                print(f"[SMTP] {addr} -> {line}")
                if in_data_mode:
                    if line == ".":
                        in_data_mode = False
                        filename = os.path.join(MAIL_OUT_DIR, f"mail_{get_timestamp()}.txt")
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write("\n".join(mail_data))
                        print(f"[SMTP] Received mail, saved to {filename}")
                        conn.sendall(b"250 OK\r\n")
                        mail_data = []
                    else:
                        mail_data.append(line)
                    continue

                cmd_parts = line.split(' ')
                if not cmd_parts: continue
                cmd = cmd_parts[0].upper()
                
                if cmd in ['HELO', 'EHLO']:
                    resp = b"250 OK\r\n"
                elif cmd == 'MAIL':
                    resp = b"250 OK\r\n"
                elif cmd == 'RCPT':
                    resp = b"250 OK\r\n"
                elif cmd == 'DATA':
                    in_data_mode = True
                    resp = b"354 Start mail input; end with <CRLF>.<CRLF>\r\n"
                elif cmd == 'QUIT':
                    conn.sendall(b"221 Bye\r\n")
                    break
                else:
                    resp = b"250 OK\r\n" # Be permissive
                conn.sendall(resp)
        except Exception as e:
            print(f"[SMTP] Handler error: {e}")
        finally:
            conn.close()
            print(f"[SMTP] Connection closed from {addr}")

    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((self.host, self.port))
            s.listen(5)
            print(f"[*] DEBUG SMTP Server listening on {self.host}:{self.port}")
            while True:
                conn, addr = s.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr)).start()
        except Exception as e:
            print(f"[SMTP] Could not start server: {e}")

# --- POP3 Server Logic ---
class Pop3Server:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def _get_mail_files(self):
        return sorted([f for f in os.listdir(MAIL_IN_DIR)
                       if os.path.isfile(os.path.join(MAIL_IN_DIR, f))])

    def _send(self, conn, addr, data):
        try:
            conn.sendall(data)
            text = data.decode('ascii', errors='replace').rstrip()
            print(f"[POP3] {addr} <- {text.split('\\r\\n')[0]} (and more...)")
        except: pass

    def handle_client(self, conn, addr):
        print(f"[POP3] Connection from {addr}")
        try:
            conn.sendall(b"+OK Fake POP3 Server Ready (DEBUG)\r\n")
            marked_for_delete = set()

            for line in line_reader(conn):
                print(f"[POP3] {addr} -> {line}")
                parts = line.split(' ')
                cmd = parts[0].upper()

                if cmd == 'USER':
                    conn.sendall(b"+OK\r\n")
                elif cmd == 'PASS':
                    conn.sendall(b"+OK Welcome\r\n")
                elif cmd == 'STAT':
                    files = self._get_mail_files()
                    total_size = sum(os.path.getsize(os.path.join(MAIL_IN_DIR, f)) for f in files)
                    conn.sendall(f"+OK {len(files)} {total_size}\r\n".encode())
                elif cmd == 'LIST':
                    files = self._get_mail_files()
                    resp = f"+OK {len(files)} messages\r\n".encode()
                    for i, f in enumerate(files):
                        size = os.path.getsize(os.path.join(MAIL_IN_DIR, f))
                        resp += f"{i+1} {size}\r\n".encode()
                    resp += b".\r\n"
                    conn.sendall(resp)
                elif cmd == 'RETR':
                    idx = int(parts[1]) - 1
                    files = self._get_mail_files()
                    if 0 <= idx < len(files):
                        filepath = os.path.join(MAIL_IN_DIR, files[idx])
                        with open(filepath, 'rb') as f:
                            content = f.read().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
                        conn.sendall(f"+OK {len(content)} octets\r\n".encode())
                        conn.sendall(content)
                        conn.sendall(b"\r\n.\r\n")
                    else:
                        conn.sendall(b"-ERR No such message\r\n")
                elif cmd == 'QUIT':
                    conn.sendall(b"+OK Bye\r\n")
                    break
                else:
                    conn.sendall(b"+OK\r\n")
        except Exception as e:
            print(f"[POP3] Handler error: {e}")
        finally:
            conn.close()
            print(f"[POP3] Connection closed from {addr}")

    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((self.host, self.port))
            s.listen(5)
            print(f"[*] DEBUG POP3 Server listening on {self.host}:{self.port}")
            while True:
                conn, addr = s.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr)).start()
        except Exception as e:
            print(f"[POP3] Could not start server: {e}")

if __name__ == '__main__':
    print("=== DEBUG Mail Server (1100/2525) for SeaMail ===")
    smtp = SmtpServer(HOST, SMTP_PORT)
    pop3 = Pop3Server(HOST, POP3_PORT)
    threading.Thread(target=smtp.start, daemon=True).start()
    threading.Thread(target=pop3.start, daemon=True).start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
