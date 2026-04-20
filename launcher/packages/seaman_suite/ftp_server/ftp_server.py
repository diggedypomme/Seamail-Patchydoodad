"""
FTP Server for SeamanUpdate.exe
Credentials from trace: irumote / muratamang
"""
import os
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

def main():
    # Root directory for FTP files
    ftp_root = os.path.join(os.path.dirname(__file__), "ftp_root")
    os.makedirs(ftp_root, exist_ok=True)

    # Create authorizer with hardcoded credentials from trace
    authorizer = DummyAuthorizer()
    authorizer.add_user("irumote", "muratamang", ftp_root, perm="elradfmw")
    authorizer.add_anonymous(ftp_root)  # Allow anonymous as fallback

    # Create handler with custom logging
    handler = FTPHandler
    handler.authorizer = authorizer

    # Override logging to show requests
    class LoggingFTPHandler(FTPHandler):
        def on_connect(self):
            print(f"\n[FTP] CLIENT CONNECTED: {self.remote_ip}:{self.remote_port}")

        def on_disconnect(self):
            print(f"[FTP] CLIENT DISCONNECTED: {self.remote_ip}")

        def on_login(self, username):
            print(f"[FTP] LOGIN: {username}")

        def on_file_sent(self, file):
            print(f"[FTP] FILE SENT: {file}")

        def on_file_received(self, file):
            print(f"[FTP] FILE RECEIVED: {file}")

        def ftp_RETR(self, path):
            print(f"[FTP] RETR (download): {path}")
            return super().ftp_RETR(path)

        def ftp_STOR(self, path):
            print(f"[FTP] STOR (upload): {path}")
            return super().ftp_STOR(path)

        def ftp_LIST(self, path):
            print(f"[FTP] LIST: {path}")
            return super().ftp_LIST(path)

        def ftp_NLST(self, path):
            print(f"[FTP] NLST: {path}")
            return super().ftp_NLST(path)

    LoggingFTPHandler.authorizer = authorizer

    # Start FTP server on port 21
    address = ('0.0.0.0', 21)
    server = FTPServer(address, LoggingFTPHandler)

    print("=== SeaMail FTP Server ===")
    print(f"Listening on 0.0.0.0:21")
    print(f"FTP Root: {ftp_root}")
    print(f"Username: irumote")
    print(f"Password: muratamang")
    print("Waiting for SeamanUpdate.exe connections...")
    print()

    server.serve_forever()

if __name__ == '__main__':
    main()
