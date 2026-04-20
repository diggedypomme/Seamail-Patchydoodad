@echo off
echo ========================================
echo  Seaman PC Database Editor V1
echo ========================================
echo.
echo Starting server on http://localhost:5073
echo.
echo Features:
echo  - Tree view with hierarchical navigation
echo  - Detail panel for viewing/editing
echo  - File history support
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

cd /d "%~dp0"
venv\Scripts\python.exe app.py

pause
