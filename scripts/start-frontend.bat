@echo off
title MultiLink Web Dashboard
cd /d "%~dp0\..\frontend"
echo [MultiLink] Starting Vite Web Dashboard on 127.0.0.1:5173...
npm.cmd run dev -- --host 127.0.0.1 --port 5173
pause
