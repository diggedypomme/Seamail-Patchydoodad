import os
from flask import Flask, request, jsonify

app = Flask(__name__)
# Ensure the fake server paths exist
ROOT_DIR = os.path.dirname(os.path.abspath(__name__))
app.config['UPLOAD_FOLDER'] = os.path.join(ROOT_DIR, 'static')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Define known routes from old win10 traces to be safe
@app.route('/test/pc/index.html', methods=['GET', 'POST'])
def test_pc_index():
    print(f"\n[HTTP] {request.method} REQUEST -> /test/pc/index.html")
    print(f"Headers:\n{request.headers}")
    print(f"Data:\n{request.get_data().decode('utf-8', errors='ignore')}")
    return "<html><body>OK1</body></html>", 200

# Catch-all route to dump any unexpected URL requests the game might make
@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    print(f"\n[HTTP CATCH-ALL] {request.method} REQUEST -> /{path}")
    print(f"Headers:\n{request.headers}")
    print(f"Data:\n{request.get_data().decode('utf-8', errors='ignore')}")
    # Return a basic 200 OK so WinInet doesn't throw a connection error immediately
    return "OK2\r\n", 200

if __name__ == '__main__':
    print("=== Fake.Seaman.TV Server ===")
    print("Listening on 0.0.0.0:80 to catch all game update requests...")
    # Port 80 is required because the hosts file redirects the standard HTTP port
    app.run(host='0.0.0.0', port=80, debug=False)
