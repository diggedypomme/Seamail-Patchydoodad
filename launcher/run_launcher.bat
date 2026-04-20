@echo off
setlocal
set "ROOT=%~dp0"
set "APP_PY=%ROOT%app.py"
set "APP_PYTHON=%ROOT%venvs\launcher-app\Scripts\python.exe"

if exist "%APP_PYTHON%" (
  start "Seaman Launcher" cmd /k ""%APP_PYTHON%" "%APP_PY%""
) else (
  echo launcher-app env not found, falling back to default Python.
  echo Run launcher\setup_launcher_app_env.bat if you want the dedicated app env first.
  start "Seaman Launcher" cmd /k "py "%APP_PY%""
)
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:5000
endlocal
