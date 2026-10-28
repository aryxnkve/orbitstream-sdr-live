<#
.SYNOPSIS
    Launches the ORBITSTREAM full-stack server locally (FastAPI + React SPA)
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         ORBITSTREAM Unified Server Launcher              " -ForegroundColor Cyan
Write-Host "       FastAPI Backend + React Production SPA             " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    Write-Host "[Python] Using project root virtual environment: $VenvPython" -ForegroundColor Green
    $PythonExe = $VenvPython
} else {
    Write-Host "[Python] Virtual environment not found, falling back to system python" -ForegroundColor Yellow
    $PythonExe = "python"
}

Write-Host "[Server] Starting ORBITSTREAM at http://localhost:8000 ..." -ForegroundColor Cyan
Write-Host "[Info] Open your web browser at: http://localhost:8000" -ForegroundColor Green
Write-Host "[Info] Press Ctrl+C at any time to stop the server." -ForegroundColor Yellow
Write-Host ""

& $PythonExe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

