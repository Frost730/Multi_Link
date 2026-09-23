@echo off
title MultiLink Backend Agent
cd /d "%~dp0\..\backend"
echo [MultiLink] Starting Local Download Engine API on 127.0.0.1:8000...
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
