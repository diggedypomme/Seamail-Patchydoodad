import socket
import threading
import os
import time
import datetime

# --- Configuration ---
SMTP_PORT = 25
POP3_PORT = 110
HOST = '0.0.0.0'  # Listen on all interfaces

MAIL_IN_DIR = 'mail_in'   # Files here are "received" by the game
MAIL_OUT_DIR = 'mail_out' # Emails sent by the game end up here

# Create directories if they don't exist
for d in [MAIL_IN_DIR, MAIL_OUT_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

def get_timestamp():
    return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

def line_reader(conn):
    """Generator to yield lines from a socket."""
    buffer = b""
    while True:
        data = conn.recv(4096)
        if not data:
            if buffer:
                yield buffer.decode('utf-8', errors='ignore')
            break
        buffer += data
        while b"\r\n" in buffer:
            line, buffer = buffer.split(b"\r\n", 1)
            yield line.decode('utf-8', errors='ignore').strip()
        # Also handle unix style lines just in case
        if b"\n" in buffer and b"\r\n" not in buffer:
            line, buffer = buffer.split(b"\n", 1)
            yield line.decode('utf-8', errors='ignore').strip()

# --- SMTP Server Logic ---
class SmtpServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def handle_client(self, conn, addr):
        print(f"[SMTP] Connection from {addr}")
        conn.sendall(b"220 Fake SMTP Server Ready\r\n")

        mail_data = []
        in_data_mode = False

        for line in line_reader(conn):
            print(f"[SMTP] {addr} -> {line}")

            if in_data_mode:
                if line == ".":
                    in_data_mode = False
                    # Save the mail
                    filename = os.path.join(MAIL_OUT_DIR, f"mail_{get_timestamp()}.txt")
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write("\n".join(mail_data))
                    print(f"[SMTP] Received mail, saved to {filename}")
                    print(f"[SMTP] Mail content ({len(mail_data)} lines):")
                    for ml in mail_data:
                        print(f"[SMTP]   | {ml}")
                    resp = b"250 OK\r\n"
                    conn.sendall(resp)
                    print(f"[SMTP] {addr} <- {resp.strip().decode()}")
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
                resp = b"221 Bye\r\n"
                conn.sendall(resp)
                print(f"[SMTP] {addr} <- {resp.strip().decode()}")
                break
            elif cmd == 'RSET':
                mail_data = []
                resp = b"250 OK\r\n"
            elif cmd == 'NOOP':
                resp = b"250 OK\r\n"
            else:
                resp = b"500 Unknown command\r\n"
            conn.sendall(resp)
            print(f"[SMTP] {addr} <- {resp.strip().decode()}")

        conn.close()
        print(f"[SMTP] Connection closed from {addr}")

    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((self.host, self.port))
            s.listen(5)
            print(f"[*] SMTP Server listening on {self.host}:{self.port}")
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
        """Get sorted list of mail files. Used by ALL commands for consistent ordering."""
        return sorted([f for f in os.listdir(MAIL_IN_DIR)
                       if os.path.isfile(os.path.join(MAIL_IN_DIR, f))])

    def _send(self, conn, addr, data, label=""):
        """Send data and log it."""
        conn.sendall(data)
        # For multi-line responses, show a summary
        text = data.decode('ascii', errors='replace').rstrip()
        lines = text.split('\r\n')
        if len(lines) <= 1:
            if lines and lines[0]:
                print(f"[POP3] {addr} <- {lines[0]}{' ' + label if label else ''}")
        else:
            print(f"[POP3] {addr} <- {lines[0]} ({len(lines)} lines){' ' + label if label else ''}")
            # for line in lines[1:]:
            #     if line:
            #         print(f"[POP3]   | {line}")

    def handle_client(self, conn, addr):
        print(f"[POP3] Connection from {addr}")
        self._send(conn, addr, b"+OK Fake POP3 Server Ready\r\n")

        # Track deletions - POP3 spec says deletes happen at QUIT
        marked_for_delete = set()

        for line in line_reader(conn):
            print(f"[POP3] {addr} -> {line}")
            parts = line.split(' ')
            cmd = parts[0].upper()

            try:
                if cmd == 'USER':
                    self._send(conn, addr, b"+OK\r\n")
                elif cmd == 'PASS':
                    self._send(conn, addr, b"+OK Welcome\r\n")
                elif cmd == 'STAT':
                    files = self._get_mail_files()
                    total_size = sum(os.path.getsize(os.path.join(MAIL_IN_DIR, f)) for f in files)
                    resp = f"+OK {len(files)} {total_size}\r\n".encode()
                    self._send(conn, addr, resp)
                elif cmd == 'LIST':
                    files = self._get_mail_files()
                    if len(parts) > 1:
                        idx = int(parts[1]) - 1
                        if 0 <= idx < len(files):
                            size = os.path.getsize(os.path.join(MAIL_IN_DIR, files[idx]))
                            resp = f"+OK {idx+1} {size}\r\n".encode()
                            self._send(conn, addr, resp, label=f"[{files[idx]}]")
                        else:
                            self._send(conn, addr, b"-ERR No such message\r\n")
                    else:
                        resp = f"+OK {len(files)} messages\r\n".encode()
                        for i, f in enumerate(files):
                            size = os.path.getsize(os.path.join(MAIL_IN_DIR, f))
                            resp += f"{i+1} {size}\r\n".encode()
                        resp += b".\r\n"
                        self._send(conn, addr, resp)
                elif cmd == 'UIDL':
                    files = self._get_mail_files()
                    if len(parts) > 1:
                        idx = int(parts[1]) - 1
                        if 0 <= idx < len(files):
                            resp = f"+OK {idx+1} {files[idx]}\r\n".encode()
                            self._send(conn, addr, resp)
                        else:
                            self._send(conn, addr, b"-ERR No such message\r\n")
                    else:
                        resp = f"+OK\r\n".encode()
                        for i, f in enumerate(files):
                            resp += f"{i+1} {f}\r\n".encode()
                        resp += b".\r\n"
                        self._send(conn, addr, resp)
                elif cmd == 'RETR':
                    idx = int(parts[1]) - 1
                    files = self._get_mail_files()
                    if 0 <= idx < len(files):
                        filepath = os.path.join(MAIL_IN_DIR, files[idx])
                        with open(filepath, 'rb') as f:
                            content = f.read().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')

                        size = len(content)
                        header = f"+OK {size} octets\r\n".encode()
                        conn.sendall(header)
                        conn.sendall(content)
                        if not content.endswith(b'\r\n'):
                            conn.sendall(b"\r\n")
                        conn.sendall(b".\r\n")
                        print(f"[POP3] {addr} <- +OK {size} octets [{files[idx]}]")
                    else:
                        self._send(conn, addr, b"-ERR No such message\r\n")
                elif cmd == 'TOP':
                    idx = int(parts[1]) - 1
                    lines_to_show = int(parts[2])
                    files = self._get_mail_files()
                    if 0 <= idx < len(files):
                        filepath = os.path.join(MAIL_IN_DIR, files[idx])
                        conn.sendall(b"+OK top follows\r\n")
                        with open(filepath, 'rb') as f:
                            raw = f.read().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
                            lines_list = raw.split(b'\r\n')
                            header_done = False
                            body_lines = 0
                            for l in lines_list:
                                conn.sendall(l + b'\r\n')
                                if not l.strip():
                                    header_done = True
                                if header_done:
                                    if body_lines >= lines_to_show: break
                                    body_lines += 1
                        conn.sendall(b".\r\n")
                        print(f"[POP3] {addr} <- +OK top follows [{files[idx]}]")
                    else:
                        self._send(conn, addr, b"-ERR No such message\r\n")
                elif cmd == 'DELE':
                    idx = int(parts[1]) - 1
                    files = self._get_mail_files()
                    if 0 <= idx < len(files):
                        marked_for_delete.add(files[idx])
                        self._send(conn, addr, b"+OK marked for deletion\r\n",
                                   label=f"[{files[idx]}]")
                    else:
                        self._send(conn, addr, b"-ERR No such message\r\n")
                elif cmd == 'RSET':
                    marked_for_delete.clear()
                    self._send(conn, addr, b"+OK\r\n")
                elif cmd == 'QUIT':
                    for fname in marked_for_delete:
                        fpath = os.path.join(MAIL_IN_DIR, fname)
                        if os.path.exists(fpath):
                            os.remove(fpath)
                            print(f"[POP3] Deleted {fname}")
                    self._send(conn, addr, b"+OK Bye\r\n")
                    break
                elif cmd == 'NOOP':
                    self._send(conn, addr, b"+OK\r\n")
                elif cmd == 'CAPA':
                    self._send(conn, addr, b"+OK Capabilities follow\r\nUSER\r\nUIDL\r\nTOP\r\n.\r\n")
                else:
                    self._send(conn, addr, f"-ERR Unknown command ({cmd})\r\n".encode())
            except Exception as e:
                print(f"[POP3] Command Error ({cmd}): {e}")
                self._send(conn, addr, b"-ERR Command error\r\n")

        conn.close()
        print(f"[POP3] Connection closed from {addr}")

    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((self.host, self.port))
            s.listen(5)
            print(f"[*] POP3 Server listening on {self.host}:{self.port}")
            while True:
                conn, addr = s.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr)).start()
        except Exception as e:
            print(f"[POP3] Could not start server: {e}")

if __name__ == '__main__':
    print("=== Fake Mail Server (SMTP/POP3) for SeaMail ===")
    print(f"  Mail inbox:  {os.path.abspath(MAIL_IN_DIR)}")
    print(f"  Mail outbox: {os.path.abspath(MAIL_OUT_DIR)}")

    smtp = SmtpServer(HOST, SMTP_PORT)
    pop3 = Pop3Server(HOST, POP3_PORT)

    threading.Thread(target=smtp.start, daemon=True).start()
    threading.Thread(target=pop3.start, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping servers...")
