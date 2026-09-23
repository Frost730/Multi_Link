@echo off
title MultiLink Master Launcher
echo ========================================================
echo               MultiLink Download Manager
echo      Intelligent Multi-Network Aggregation Engine
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/2] Launching Backend Engine (127.0.0.1:8000)...
start "MultiLink Backend Engine" cmd /k "scripts\start-backend.bat"

timeout /t 2 /nobreak >nul

echo [2/2] Launching Frontend Dashboard (127.0.0.1:5173)...
start "MultiLink Dashboard" cmd /k "scripts\start-frontend.bat"

echo.
echo MultiLink is starting up!
echo Dashboard will be available at: http://127.0.0.1:5173
echo.
pause
