# GEM Var Tracker - Setup & Launch

Real-time memory polling and visualization for `Seaman.exe`.

## 🚀 Quick Start

1.  **Install Dependencies**:
    ```powershell
    pip install -r requirements.txt
    ```

2.  **Start the Dashboard (Flask)**:
    ```powershell
    python app.py
    ```
    *Access at http://localhost:5081*

3.  **Launch the Game**:
    Start `Seaman.exe` and ensure it's running.

4.  **Start the Polling Engine (Frida)**:
    ```powershell
    python scripts/tracker_engine.py
    ```

## 📂 Project Structure
- `app.py`: Flask server & SocketIO coordinator.
- `scripts/scanner.js`: Frida agent for memory access.
- `scripts/tracker_engine.py`: Python controller for polling & logging.
- `scripts/variables.json`: Configuration for memory addresses and offsets.
- `templates/dashboard.html`: Real-time visualization UI.
- `logs/`: CSV session logs.

## 🛠️ Adding New Variables
Open `scripts/variables.json` and add a new entry to the `high_value` array:
```json
{
  "name": "My New Var",
  "address": "0x0046XXXX",
  "offsets": [0x10, 0x04],
  "type": "float"
}
```
The engine will pick it up automatically on the next restart.
