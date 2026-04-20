@echo off
REM Quick Start script for Weather Server
REM Run this to set up and start the weather server

echo ============================================================
echo Seaman PC - Weather Server Quick Start
echo ============================================================
echo.

REM Check if venv exists
if not exist "venv\" (
    echo [1/4] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create venv
        pause
        exit /b 1
    )
    echo Done!
    echo.
) else (
    echo [1/4] Virtual environment already exists
    echo.
)

REM Install requirements
echo [2/4] Installing dependencies...
call venv\Scripts\activate.bat
pip install -q -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements
    pause
    exit /b 1
)
echo Done!
echo.

REM Check DLL patch status
echo [3/4] Checking WeatherGet.dll patch status...
python test_patch.py
echo.

REM Ask if user wants to patch
set /p PATCH="Do you want to patch the DLL now? (y/n): "
if /i "%PATCH%"=="y" (
    echo Patching DLL...
    python patch_weather_dll.py
    echo.
)

REM Start server
echo [4/4] Starting weather server...
echo.
echo Server will start on http://localhost:8080
echo Press Ctrl+C to stop the server
echo.
echo ============================================================
echo.

python weather_mock.py

pause
