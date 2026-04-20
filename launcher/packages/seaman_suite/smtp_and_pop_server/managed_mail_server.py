import datetime
import os
import socket
import threading
import time

from mailbox_store import MailboxStore


SMTP_PORT = 25
POP3_PORT = 110
HOST = "0.0.0.0"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORE = MailboxStore(BASE_DIR)


def get_timestamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def line_reader(conn):
    buffer = b""
    while True:
        data = conn.recv(4096)
        if not data:
            if buffer:
                yield buffer.decode("utf-8", errors="ignore")
            break
        buffer += data
        while b"\r\n" in buffer:
            line, buffer = buffer.split(b"\r\n", 1)
            yield line.decode("utf-8", errors="ignore").strip()
        if b"\n" in buffer and b"\r\n" not in buffer:
            line, buffer = buffer.split(b"\n", 1)
            yield line.decode("utf-8", errors="ignore").strip()


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
                    filename = os.path.join(BASE_DIR, "mail_out", f"mail_{get_timestamp()}.txt")
                    with open(filename, "w", encoding="utf-8") as handle:
                        handle.write("\n".join(mail_data))
                    print(f"[SMTP] Received mail, saved to {filename}")
                    conn.sendall(b"250 OK\r\n")
                    mail_data = []
                else:
                    mail_data.append(line)
                continue

            cmd_parts = line.split(" ")
            if not cmd_parts:
                continue
            cmd = cmd_parts[0].upper()

            if cmd in ["HELO", "EHLO", "MAIL", "RCPT", "RSET", "NOOP"]:
                response = b"250 OK\r\n"
            elif cmd == "DATA":
                in_data_mode = True
                response = b"354 Start mail input; end with <CRLF>.<CRLF>\r\n"
            elif cmd == "QUIT":
                response = b"221 Bye\r\n"
                conn.sendall(response)
                break
            else:
                response = b"500 Unknown command\r\n"

            conn.sendall(response)

        conn.close()
        print(f"[SMTP] Connection closed from {addr}")

    def start(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((self.host, self.port))
            server.listen(5)
            print(f"[*] SMTP Server listening on {self.host}:{self.port}")
            while True:
                conn, addr = server.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()
        except Exception as exc:
            print(f"[SMTP] Could not start server: {exc}")


class Pop3Server:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def _get_mail_files(self):
        inbox = STORE.list_inbox_messages()["messages"]
        return [message["filename"] for message in inbox if message.get("enabled")]

    def _send(self, conn, addr, data, label=""):
        conn.sendall(data)
        text = data.decode("ascii", errors="replace").rstrip()
        lines = text.split("\r\n")
        if len(lines) <= 1:
            if lines and lines[0]:
                print(f"[POP3] {addr} <- {lines[0]}{' ' + label if label else ''}")
        else:
            print(f"[POP3] {addr} <- {lines[0]} ({len(lines)} lines){' ' + label if label else ''}")

    def handle_client(self, conn, addr):
        print(f"[POP3] Connection from {addr}")
        self._send(conn, addr, b"+OK Fake POP3 Server Ready\r\n")
        marked_for_delete = set()

        for line in line_reader(conn):
            print(f"[POP3] {addr} -> {line}")
            parts = line.split(" ")
            cmd = parts[0].upper()

            try:
                if cmd == "USER":
                    self._send(conn, addr, b"+OK\r\n")
                elif cmd == "PASS":
                    self._send(conn, addr, b"+OK Welcome\r\n")
                elif cmd == "STAT":
                    files = self._get_mail_files()
                    total_size = sum(os.path.getsize(os.path.join(BASE_DIR, "mail_in", filename)) for filename in files)
                    self._send(conn, addr, f"+OK {len(files)} {total_size}\r\n".encode())
                elif cmd == "LIST":
                    files = self._get_mail_files()
                    if len(parts) > 1:
                        idx = int(parts[1]) - 1
                        if 0 <= idx < len(files):
                            size = os.path.getsize(os.path.join(BASE_DIR, "mail_in", files[idx]))
                            self._send(conn, addr, f"+OK {idx+1} {size}\r\n".encode(), label=f"[{files[idx]}]")
                        else:
                            self._send(conn, addr, b"-ERR No such message\r\n")
                    else:
                        response = f"+OK {len(files)} messages\r\n".encode()
                        for index, filename in enumerate(files):
                            size = os.path.getsize(os.path.join(BASE_DIR, "mail_in", filename))
                            response += f"{index+1} {size}\r\n".encode()
                        response += b".\r\n"
                        self._send(conn, addr, response)
                elif cmd == "UIDL":
                    files = self._get_mail_files()
                    if len(parts) > 1:
                        idx = int(parts[1]) - 1
                        if 0 <= idx < len(files):
                            self._send(conn, addr, f"+OK {idx+1} {files[idx]}\r\n".encode())
                        else:
                            self._send(conn, addr, b"-ERR No such message\r\n")
                    else:
                        response = b"+OK\r\n"
                        for index, filename in enumerate(files):
                            response += f"{index+1} {filename}\r\n".encode()
                        response += b".\r\n"
                        self._send(conn, addr, response)
                elif cmd == "RETR":
                    idx = int(parts[1]) - 1
                    files = self._get_mail_files()
                    if 0 <= idx < len(files):
                        filepath = os.path.join(BASE_DIR, "mail_in", files[idx])
                        with open(filepath, "rb") as handle:
                            content = handle.read().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")

                        size = len(content)
                        conn.sendall(f"+OK {size} octets\r\n".encode())
                        conn.sendall(content)
                        if not content.endswith(b"\r\n"):
                            conn.sendall(b"\r\n")
                        conn.sendall(b".\r\n")
                        STORE.mark_message_pulled_by_filename(files[idx])
                    else:
                        self._send(conn, addr, b"-ERR No such message\r\n")
                elif cmd == "TOP":
                    idx = int(parts[1]) - 1
                    lines_to_show = int(parts[2])
                    files = self._get_mail_files()
                    if 0 <= idx < len(files):
                        filepath = os.path.join(BASE_DIR, "mail_in", files[idx])
                        conn.sendall(b"+OK top follows\r\n")
                        with open(filepath, "rb") as handle:
                            raw = handle.read().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
                            lines_list = raw.split(b"\r\n")
                            header_done = False
                            body_lines = 0
                            for item in lines_list:
                                conn.sendall(item + b"\r\n")
                                if not item.strip():
                                    header_done = True
                                if header_done:
                                    if body_lines >= lines_to_show:
                                        break
                                    body_lines += 1
                        conn.sendall(b".\r\n")
                    else:
                        self._send(conn, addr, b"-ERR No such message\r\n")
                elif cmd == "DELE":
                    idx = int(parts[1]) - 1
                    files = self._get_mail_files()
                    if 0 <= idx < len(files):
                        marked_for_delete.add(files[idx])
                        self._send(conn, addr, b"+OK marked for deletion\r\n", label=f"[{files[idx]}]")
                    else:
                        self._send(conn, addr, b"-ERR No such message\r\n")
                elif cmd == "RSET":
                    marked_for_delete.clear()
                    self._send(conn, addr, b"+OK\r\n")
                elif cmd == "QUIT":
                    for filename in marked_for_delete:
                        STORE.mark_message_pulled_by_filename(filename)
                    self._send(conn, addr, b"+OK Bye\r\n")
                    break
                elif cmd == "NOOP":
                    self._send(conn, addr, b"+OK\r\n")
                elif cmd == "CAPA":
                    self._send(conn, addr, b"+OK Capabilities follow\r\nUSER\r\nUIDL\r\nTOP\r\n.\r\n")
                else:
                    self._send(conn, addr, f"-ERR Unknown command ({cmd})\r\n".encode())
            except Exception as exc:
                print(f"[POP3] Command Error ({cmd}): {exc}")
                self._send(conn, addr, b"-ERR Command error\r\n")

        conn.close()
        print(f"[POP3] Connection closed from {addr}")

    def start(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((self.host, self.port))
            server.listen(5)
            print(f"[*] POP3 Server listening on {self.host}:{self.port}")
            while True:
                conn, addr = server.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()
        except Exception as exc:
            print(f"[POP3] Could not start server: {exc}")


def run_servers(smtp_port: int, pop3_port: int, title: str) -> None:
    STORE.list_inbox_messages()
    print(title)
    print(f"  Mail inbox:  {os.path.abspath(os.path.join(BASE_DIR, 'mail_in'))}")
    print(f"  Mail outbox: {os.path.abspath(os.path.join(BASE_DIR, 'mail_out'))}")

    smtp = SmtpServer(HOST, smtp_port)
    pop3 = Pop3Server(HOST, pop3_port)

    threading.Thread(target=smtp.start, daemon=True).start()
    threading.Thread(target=pop3.start, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping servers...")


if __name__ == "__main__":
    run_servers(SMTP_PORT, POP3_PORT, "=== Managed Mail Server (SMTP/POP3) for SeaMail ===")
