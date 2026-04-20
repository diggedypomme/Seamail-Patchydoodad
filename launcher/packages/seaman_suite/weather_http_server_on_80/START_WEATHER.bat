@echo off
REM Start weather server on port 80
REM Requires Administrator privileges

echo Starting Seaman PC Weather Server on port 80...
echo.

REM Check if venv exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo ============================================================
echo Weather server starting on http://192.168.0.6:80
echo.
echo Make sure on XP hosts file you have:
echo   192.168.0.6  www.jma.go.jp
echo.
echo Press Ctrl+C to stop server
echo ============================================================
echo.

python simple_weather_server.py 80

pause
