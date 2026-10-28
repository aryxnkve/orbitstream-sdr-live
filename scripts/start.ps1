# ORBITSTREAM — Local Windows PowerShell Startup Script
# SIH260002: Integrated Satellite Stream Troubleshooting Platform

param (
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "               ORBITSTREAM Startup Script                 " -ForegroundColor Cyan
Write-Host "   Offline Satellite Stream Analysis & Troubleshooting   " -ForegroundColor DarkGray
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# Verify Python
Write-Host "[1/4] Checking Python environment..." -ForegroundColor Yellow
try {
    $pythonVer = python --version
    Write-Host "      Found: $pythonVer" -ForegroundColor Green
} catch {
    Write-Host "      ERROR: Python was not found in PATH." -ForegroundColor Red
    Write-Host "      Please install Python 3.11+ and try again." -ForegroundColor Red
    exit 1
}

# Verify Node.js
Write-Host "[2/4] Checking Node.js environment..." -ForegroundColor Yellow
try {
    $nodeVer = node --version
    Write-Host "      Found Node.js: $nodeVer" -ForegroundColor Green
} catch {
    Write-Host "      ERROR: Node.js was not found in PATH." -ForegroundColor Red
    Write-Host "      Please install Node.js (v18+) and try again." -ForegroundColor Red
    exit 1
}

$rootDir = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $rootDir "backend"
$frontendDir = Join-Path $rootDir "frontend"
$venvPython = Join-Path $rootDir ".venv\Scripts\python.exe"
$pythonCmd = if (Test-Path $venvPython) { $venvPython } else { "python" }

Write-Host "[3/4] Launching FastAPI backend on http://127.0.0.1:$BackendPort..." -ForegroundColor Yellow
$backendProcess = Start-Process $pythonCmd -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort" -WorkingDirectory $backendDir -PassThru

Write-Host "[4/4] Launching Vite frontend on http://127.0.0.1:$FrontendPort..." -ForegroundColor Yellow
$frontendProcess = Start-Process npm -ArgumentList "run dev -- --host 127.0.0.1 --port $FrontendPort" -WorkingDirectory $frontendDir -PassThru

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "       ORBITSTREAM is now running locally!                " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  Frontend URL: http://127.0.0.1:$FrontendPort" -ForegroundColor Cyan
Write-Host "  Backend API:  http://127.0.0.1:$BackendPort/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press [CTRL + C] or close this window to stop both servers." -ForegroundColor Gray
Write-Host ""

try {
    # Keep script open and monitor processes
    while ($true) {
        Start-Sleep -Seconds 2
        if ($backendProcess.HasExited -or $frontendProcess.HasExited) {
            Write-Host "One of the services stopped." -ForegroundColor Yellow
            break
        }
    }
} finally {
    Write-Host "Shutting down ORBITSTREAM..." -ForegroundColor DarkGray
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($frontendProcess -and -not $frontendProcess.HasExited) {
        Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "ORBITSTREAM stopped cleanly." -ForegroundColor Green
}
