# Seaman Infrastructure Suite - Technical Summary

This document provides a comprehensive overview of the specialized servers, proxies, and modification tools developed for the Seaman Mail Server restoration and enhancement project. These tools are consolidated in the `seaman_suite` directory for integration into the local launcher.

## 📡 Communication & Service Servers
These scripts emulate the legacy Seaman / JMA network infrastructure to restore full game functionality.

### [SMTP & POP Server](file:///C:/2026_projects/seaman_ghi_final/launcher/packages/seaman_suite/smtp_and_pop_server/)
*   **Purpose**: Restores the "SeaMail" ecosystem.
*   **Key Files**: `mail_server.py` (Standard), `mail_server_debug.py` (Win11 Fix).
*   **Mechanism**: Implements a surgical POP3/SMTP relay. Supports non-standard ports (1100/2525) to bypass modern OS firewall resets.
*   **Storage**: Direct file-to-mail injection via `mail_in/` and `mail_out/` folders.

### [Dual HTTP + FTP Server](file:///C:/2026_projects/seaman_ghi_final/launcher/packages/seaman_suite/ftp_server/)
*   **Purpose**: Handles legacy file updates and web requests.
*   **Key File**: `dual_server.py`.
*   **Mechanism**: Runs a simultaneous `pyftpdlib` instance (Port 21) and a Flask HTTP server (Port 80).
*   **Research Note**: Hardcoded with authentic credentials found in traces: `irumote / muratamang`.

### [Weather Redirection Server](file:///C:/2026_projects/seaman_ghi_final/launcher/packages/seaman_suite/weather_http_server_on_80/)
*   **Purpose**: Spoofs the Japanese Meteorological Agency (JMA) to control in-game weather.
*   **Key Files**: `weather_mock.py`, `patch_weather_dll.py`.
*   **Mechanism**: Redirects hardcoded JMA URLs in `WeatherGet.dll` to `localhost:8080` (or `127.0.0.1:80`).
*   **Result**: Allows real-time manipulation of Seaman's environmental variables (Rain, Snow, Temp).

---

## 🗄️ Database Management Tools
Advanced tools for reading and modifying the Seaman `AitDB` (.udb) save files.

### [Main DB Manager V2](file:///C:/2026_projects/seaman_ghi_final/launcher/packages/seaman_suite/db_manager_main/)
*   **Feature**: A premium Flask dashboard (`app_v2.py`) for live database editing.
*   **Technology**: Uses a custom **IDEA Cipher** engine (`idea_cipher.py`) to decrypt/encrypt save records.
*   **UX**: Includes auto-refreshing table views, change-tracking highlights, and "Combined File" monitoring across Seaman/User/Calendar databases.

### [Database Proxy Analyzer](file:///C:/2026_projects/seaman_ghi_final/launcher/packages/seaman_suite/db_manager_proxy/)
*   **Purpose**: Real-time traffic analysis of Seaman's internal database calls.
*   **Mechanism**: Intercepts `SET`/`GET` commands over UDP Port 5075/9999.
*   **Insight**: Identifies new variable paths (e.g., `Bio\Hunger`) even if they haven't been saved to disk yet.

---

## 👁️ Overlays & Real-Time Tracking
Visualization engines for monitoring Seaman's physical state in memory.

### [GEM Var Tracker](file:///C:/2026_projects/seaman_ghi_final/launcher/packages/seaman_suite/seaman_variable_tracker/)
*   **Focus**: Massive-scale variable polling (280+ fields).
*   **Technique**: Hybrid Hook-then-Poll system. Uses Frida to find base pointers, then high-speed Windows `ReadProcessMemory`.

### [3D Position Tracker](file:///C:/2026_projects/seaman_ghi_final/launcher/packages/seaman_suite/position_tracker_bridge/)
*   **Visuals**: A Three.js viewer that plots Seaman's XYZ coordinates in a 3D tank.
*   **Relay**: Receives UDP telemetry from the XP machine to display real-time movement on a modern dashboard.

### [Interactive Menu Overlay](file:///C:/2026_projects/seaman_ghi_final/launcher/packages/seaman_suite/cli_screensaver_menu/)
*   **Type**: Transparent Tkinter Overlay.
*   **Integration**: Anchors translated speech bubbles and interactive menus (Spin/Tickle) directly relative to Seaman's head position in the game window.

---

## 🛠️ Binary Patching & Persistence
Core infrastructure for maintaining a stable modded environment.

### [Surgical Patcher](file:///C:/2026_projects/seaman_ghi_final/launcher/packages/seaman_suite/patcher/)
*   **Concept**: A Master/Workspace system that ensures original game files are never permanently altered.
*   **Logic**: Performs hex diffing and byte verification before applying mod patches.

### [App Persistence Suite](file:///C:/2026_projects/seaman_ghi_final/launcher/packages/seaman_suite/force_persistent_apps/)
*   **Utility**: Scripts like `force_persistent_office.py` that spoof Windows registry/window states to keep specific background services active for Seaman's AI.
