@echo off
title Install BSF Detection System
set "APP_DIR=%~dp0pg"
cd /d "%APP_DIR%"

echo ============================================
echo   Installing the BSF Detection System
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on this computer.
    echo Please install Python from https://www.python.org/downloads/ first.
    echo ^(Select "Add Python to PATH" during installation.^)
    pause
    exit /b 1
)

echo [1/3] Creating the virtual environment...
python -m venv "%APP_DIR%\venv"

echo [2/3] Installing required libraries...
"%APP_DIR%\venv\Scripts\python.exe" -m pip install --upgrade pip >nul
"%APP_DIR%\venv\Scripts\python.exe" -m pip install -r "%APP_DIR%\requirements.txt"

echo [3/3] Finished!
echo.
echo ============================================
echo   Installation complete! Double-click ..\run.bat
echo   to open the application.
echo ============================================
pause
