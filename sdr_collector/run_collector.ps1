# ORBITSTREAM RTL-SDR Collector Windows PowerShell Startup Script
# SIH260002: Integrated Satellite Stream Troubleshooting Platform

param (
    [string]$BackendUrl,
    [string]$ApiKey,
    [int]$Frequency,
    [string]$Mode = "hardware",
    [switch]$Once,
    [switch]$Demo
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         ORBITSTREAM RTL-SDR Collector Launcher           " -ForegroundColor Cyan
Write-Host "       Physical Layer Telemetry & Spectrum Monitor        " -ForegroundColor DarkGray
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# Determine root repository directory and virtual environment
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir

# Check virtual environment
$venvPython = Join-Path $rootDir ".venv\Scripts\python.exe"
$localVenvPython = Join-Path $scriptDir ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $pythonCmd = $venvPython
    Write-Host "[Python] Using project root virtual environment: $venvPython" -ForegroundColor Green
} elseif (Test-Path $localVenvPython) {
    $pythonCmd = $localVenvPython
    Write-Host "[Python] Using collector virtual environment: $localVenvPython" -ForegroundColor Green
} else {
    $pythonCmd = "python"
    Write-Host "[Python] Virtual environment not found, falling back to system python" -ForegroundColor Yellow
}

# Build arguments
$collectorArgs = @("-m", "sdr_collector.collector")

if ($Demo) {
    $collectorArgs += @("--mode", "demo")
} elseif ($Mode) {
    $collectorArgs += @("--mode", $Mode)
}

if ($BackendUrl) {
    $collectorArgs += @("--backend-url", $BackendUrl)
}

if ($ApiKey) {
    $collectorArgs += @("--api-key", $ApiKey)
}

if ($Frequency) {
    $collectorArgs += @("--frequency", $Frequency)
}

if ($Once) {
    $collectorArgs += "--once"
}

Write-Host "[Launcher] Starting collector from $rootDir..." -ForegroundColor Yellow
Set-Location $rootDir

try {
    & $pythonCmd $collectorArgs
} catch {
    Write-Host "[Error] Collector exited with error: $_" -ForegroundColor Red
}

