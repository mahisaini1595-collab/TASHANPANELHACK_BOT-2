@echo off
title TASHANPANELHACK BOT
echo Checking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    pause
    exit /b
)

echo Installing dependencies...
pip install -r requirements.txt

echo Starting Bot...
:run
python main.py
echo Bot crashed or stopped. Restarting in 5 seconds...
timeout /t 5
goto run
