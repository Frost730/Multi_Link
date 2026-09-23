# MultiLink Master PowerShell Startup Script
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "               MultiLink Download Manager               " -ForegroundColor White
Write-Host "      Intelligent Multi-Network Aggregation Engine      " -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$RootPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootPath

Write-Host "[1/2] Launching Backend Agent (127.0.0.1:8000)..." -ForegroundColor Yellow
Start-Process cmd.exe -ArgumentList "/k `"$RootPath\scripts\start-backend.bat`""

Start-Sleep -Seconds 2

Write-Host "[2/2] Launching Frontend Dashboard (127.0.0.1:5173)..." -ForegroundColor Yellow
Start-Process cmd.exe -ArgumentList "/k `"$RootPath\scripts\start-frontend.bat`""

Write-Host ""
Write-Host "MultiLink is running!" -ForegroundColor Green
Write-Host "Dashboard: " -NoNewline
Write-Host "http://127.0.0.1:5173" -ForegroundColor Cyan
Write-Host "Backend API Docs: " -NoNewline
Write-Host "http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host ""
