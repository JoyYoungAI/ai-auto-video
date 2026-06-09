@echo off
chcp 65001 >nul 2>&1
echo ================================================
echo  AI Story Video Generator - NVIDIA NIM
echo ================================================
echo.

where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo uv not found. Installing uv...
    powershell -Command "irm https://astral.sh/uv/install.ps1 | iex"
    echo Please restart this window and run start.bat again.
    pause
    exit /b 1
)

echo [1/2] Syncing dependencies with uv...
uv sync
if %errorlevel% neq 0 (
    echo ERROR: uv sync failed.
    pause
    exit /b 1
)
echo.

echo [2/2] Starting server...
echo.
echo  Open browser: http://localhost:5000
echo  Press Ctrl+C to stop
echo.
set PYTHONUTF8=1
.venv\Scripts\python.exe video_server.py

pause
