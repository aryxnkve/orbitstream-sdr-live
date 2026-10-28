@echo off
setlocal
cd /d "%~dp0"

echo ==========================================================
echo          ORBITSTREAM Unified Server Launcher
echo        FastAPI Backend + React Production SPA
echo ==========================================================
echo.

if exist ".venv\Scripts\python.exe" (
    echo [Python] Using local virtual environment: .venv
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    echo [Python] Using system python
    set "PYTHON_EXE=python"
)

echo [Server] Starting ORBITSTREAM at http://localhost:8000 ...
echo [Info] Open your web browser at: http://localhost:8000
echo [Info] Press Ctrl+C at any time to stop the server.
echo.

"%PYTHON_EXE%" -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

pause

