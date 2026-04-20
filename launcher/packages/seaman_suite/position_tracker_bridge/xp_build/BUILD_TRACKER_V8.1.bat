@echo off
echo ========================================
echo Building Seaman Tracker v8.1
echo ========================================
echo.

call "C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\VC\Auxiliary\Build\vcvars32.bat" >nul 2>&1

echo Compiling xp_debug_tracker_v8.1.cpp...
echo.

cl /D_WIN32_WINNT=0x0501 ^
   xp_debug_tracker_v8.1.cpp ^
   /Fe:xp_debug_tracker_v8.1.exe ^
   /link /SUBSYSTEM:CONSOLE,5.01 ws2_32.lib

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Build successful!
    echo ========================================
    echo.
    echo Output: xp_debug_tracker_v8.1.exe
    echo.
    echo VERSION 8.1 - Synced with bridge8_1.py
    echo   + Network mode ON by default
    echo   + Sends to 192.168.0.6:8888 automatically
    echo   + Debugger stays attached (stable approach)
    echo   + Pairs with bridge8_1.py for semantic labels
    echo.
    echo REQUIREMENTS:
    echo   - Database.dll UDP streaming must be DISABLED
    echo   - Use bridge8_1.py on dev machine (port 8888)
    echo.
    echo Usage:
    echo   xp_debug_tracker_v8.1.exe              network to 192.168.0.6
    echo   xp_debug_tracker_v8.1.exe --csv        network + CSV logging
    echo   xp_debug_tracker_v8.1.exe --ip=X.X.X.X network to custom IP
    echo.
    echo On dev machine:
    echo   python bridge8_1.py
    echo.
    echo DIFFERENCES FROM v8:
    echo   - Same tracker code
    echo   - Version number synced with bridge8_1.py
    echo   - Bridge has semantic labels ("Location X" not "Position X")
    echo   - Bridge has 3D preview
    echo   - Bridge has view mode buttons
    echo.
) else (
    echo.
    echo Build FAILED!
    echo.
)

pause
