from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import os
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gem-tracker-secret'
socketio = SocketIO(app, cors_allowed_origins="*")
TRACKER_PORT = 5081

# Shared state for dashboard
latest_variables = {}
polling_frequency = 0.5

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/config', methods=['GET', 'POST'])
def config_api():
    config_path = os.path.join(os.path.dirname(__file__), "scripts", "variables.json")
    if request.method == 'POST':
        # Potential to update variables on-the-fly
        new_config = request.json
        with open(config_path, "w") as f:
            json.dump(new_config, f, indent=2)
        return jsonify({"status": "updated"})
    
    with open(config_path, "r") as f:
        return jsonify(json.load(f))

@socketio.on('connect')
def handle_connect():
    print("[Flask] Dashboard Connected")
    emit('sync_state', {"variables": latest_variables, "frequency": polling_frequency})

@socketio.on('variable_update')
@socketio.on('engine_update')
def handle_update(data):
    global latest_variables
    latest_variables = data.get("variables", {})
    # Broadcast to all connected dashboards
    emit('dashboard_update', data, broadcast=True)

@socketio.on('update_frequency')
def handle_frequency(data):
    global polling_frequency
    polling_frequency = data.get("frequency", 0.5)
    # Broadcast to engine
    emit('set_frequency', {"frequency": polling_frequency}, broadcast=True)

if __name__ == '__main__':
    print("=" * 60)
    print("GEM Var Tracker Dashboard")
    print(f"  URL: http://localhost:{TRACKER_PORT}")
    print("=" * 60)
    socketio.run(app, host='0.0.0.0', port=TRACKER_PORT, debug=False)
