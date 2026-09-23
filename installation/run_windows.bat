@echo off
rem Starts Sprite Drawer on Windows. Run installation\install_windows.bat once first.

cd /d "%~dp0.."
title Sprite Drawer

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Sprite Drawer is not installed yet. Double-click install_windows.bat first.
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
