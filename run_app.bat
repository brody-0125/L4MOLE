@echo off
chcp 65001 > nul
title Local Semantic Explorer
cd /d "%~dp0"

echo ==========================================
echo   Local Semantic Explorer
echo ==========================================
echo.

REM Check for virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo.
    echo Please run one of the following first:
    echo   python setup_app.py
    echo   python launcher.py
    echo.
    pause
    exit /b 1
)

echo Starting application...
.venv\Scripts\python.exe main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application exited with an error.
    echo.
    pause
)
