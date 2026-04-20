@echo off
echo ========================================
echo  Seaman PC Database Editor V2
echo ========================================
echo.
echo Starting server on http://localhost:5074
echo.
echo Features:
echo  - Table view with inline editing
echo  - Auto-refresh with change tracking
echo  - Change log panel
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

cd /d "%~dp0"
venv\Scripts\python.exe app_v2.py

pause
