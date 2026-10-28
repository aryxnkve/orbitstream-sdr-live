@echo off
setlocal
cd /d "%~dp0"

echo ==========================================================
echo         ORBITSTREAM RTL-SDR Collector Launcher
echo ==========================================================
echo.

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo [Collector] Launching RTL-SDR hardware collector...
echo [Info] Make sure your RTL-SDR USB dongle is plugged in.
echo [Info] Press Ctrl+C at any time to stop collecting.
echo.

"%PYTHON_EXE%" -m sdr_collector.collector %*

pause

