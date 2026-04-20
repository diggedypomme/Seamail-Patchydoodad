"""
Dual HTTP + FTP Server for SeaMail
Runs both servers simultaneously in separate threads
"""
import os
import threading
from flask import Flask, request
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

# === HTTP Server (Flask) ===
app = Flask(__name__)
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(ROOT_DIR, 'static')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/test/pc/index.html', methods=['GET', 'POST'])
def test_pc_index():
    print(f"\n[HTTP] {request.method} REQUEST -> /test/pc/index.html")
    print(f"Headers:\n{request.headers}")
    print(f"Data:\n{request.get_data().decode('utf-8', errors='ignore')}")
    return "<html><body>OK1</body></html>", 200

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    print(f"\n[HTTP] {request.method} REQUEST -> /{path}")
    print(f"Headers:\n{request.headers}")
    print(f"Data:\n{request.get_data().decode('utf-8', errors='ignore')}")
    return "OK2\r\n", 200

# === FTP Server ===
class LoggingFTPHandler(FTPHandler):
    def on_connect(self):
        print(f"\n[FTP] CLIENT CONNECTED: {self.remote_ip}:{self.remote_port}")

    def on_disconnect(self):
        print(f"[FTP] CLIENT DISCONNECTED: {self.remote_ip}")

    def on_login(self, username):
        print(f"[FTP] LOGIN SUCCESS: {username}")

    def on_login_failed(self, username, password):
        print(f"[FTP] LOGIN FAILED: {username} / {password}")

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

    def ftp_CWD(self, path):
        print(f"[FTP] CWD (change directory): {path}")
        return super().ftp_CWD(path)

def run_ftp_server():
    """Run FTP server in separate thread"""
    ftp_root = os.path.join(ROOT_DIR, "ftp_root")
    os.makedirs(ftp_root, exist_ok=True)

    authorizer = DummyAuthorizer()
    # Credentials from API trace: irumote / muratamang
    authorizer.add_user("irumote", "muratamang", ftp_root, perm="elradfmw")
    authorizer.add_anonymous(ftp_root, perm="elr")

    LoggingFTPHandler.authorizer = authorizer
    address = ('0.0.0.0', 21)
    server = FTPServer(address, LoggingFTPHandler)

    print(f"[FTP SERVER] Listening on 0.0.0.0:21")
    print(f"[FTP SERVER] Root: {ftp_root}")
    print(f"[FTP SERVER] User: irumote / muratamang\n")

    server.serve_forever()

def run_http_server():
    """Run Flask HTTP server"""
    print(f"[HTTP SERVER] Listening on 0.0.0.0:80\n")
    app.run(host='0.0.0.0', port=80, debug=False, use_reloader=False)

if __name__ == '__main__':
    print("=" * 50)
    print("   DUAL HTTP+FTP SERVER FOR SEAMAIL")
    print("=" * 50)
    print()

    # Start FTP server in background thread
    ftp_thread = threading.Thread(target=run_ftp_server, daemon=True)
    ftp_thread.start()

    # Run HTTP server in main thread (blocks)
    run_http_server()
