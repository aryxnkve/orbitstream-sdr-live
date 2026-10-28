@echo off
REM ORBITSTREAM RTL-SDR Collector Windows Batch Launcher
setlocal

cd /d "%~dp0\.."

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo Starting ORBITSTREAM RTL-SDR Collector...
"%PYTHON_EXE%" -m sdr_collector.collector %*

pause

