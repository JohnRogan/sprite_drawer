@echo off
rem Sprite Drawer installer for Windows.
rem Installs Python 3.14 for the current user (if missing), creates a private
rem .venv in the project folder, and installs the packages from requirements.txt.

setlocal
cd /d "%~dp0.."
title Sprite Drawer - Install

set "PY_VERSION=3.14.3"
set "ARCH=amd64"
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "ARCH=arm64"
if /i "%PROCESSOR_ARCHITEW6432%"=="ARM64" set "ARCH=arm64"

echo.
echo ==============================================
echo   Sprite Drawer installer (Windows)
echo ==============================================
echo.

echo [1/3] Checking for Python 3.14...
call :find_python
if defined PY goto have_python

echo       Not found. Downloading Python %PY_VERSION% from python.org...
set "PY_INSTALLER=%TEMP%\python-%PY_VERSION%-%ARCH%.exe"
curl.exe -L --fail --progress-bar -o "%PY_INSTALLER%" "https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-%ARCH%.exe"
if errorlevel 1 (
    set "ERR=Could not download Python. Check your internet connection and try again."
    goto fail
)
echo       Installing Python (about a minute, no clicks needed)...
"%PY_INSTALLER%" /quiet InstallAllUsers=0 InstallLauncherAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0
if errorlevel 1 (
    set "ERR=Python could not be installed."
    goto fail
)
del "%PY_INSTALLER%" >nul 2>&1
call :find_python
if not defined PY (
    set "ERR=Python was installed but could not be found. Restart your PC and run this installer again."
    goto fail
)

:have_python
echo       Found: %PY%

echo.
echo [2/3] Setting up Sprite Drawer's private Python environment...
if not exist ".venv\Scripts\python.exe" goto make_venv
".venv\Scripts\python.exe" -c "import sys; sys.exit(sys.version_info[:2] != (3, 14))" >nul 2>&1
if errorlevel 1 goto make_venv
echo       Already set up.
goto install_packages

:make_venv
if exist ".venv" rmdir /s /q ".venv"
"%PY%" -m venv .venv
if errorlevel 1 (
    set "ERR=Could not create the environment."
    goto fail
)
echo       Done.

:install_packages
echo.
echo [3/3] Installing packages (this can take a few minutes)...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade pip
if errorlevel 1 (
    set "ERR=Could not update pip. Check your internet connection and try again."
    goto fail
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    set "ERR=Could not install packages. Check your internet connection and try again."
    goto fail
)
".venv\Scripts\python.exe" -c "import PySide6.QtWidgets, PySide6.QtPdf, PIL, pillow_heif"
if errorlevel 1 (
    set "ERR=Packages installed but could not be loaded."
    goto fail
)

echo.
echo ==============================================
echo   Install complete!
echo   Next: read CONTROLS.md, then double-click
echo   run_windows.bat to start the app.
echo ==============================================
echo.
pause
exit /b 0

:fail
echo.
echo INSTALL FAILED: %ERR%
echo.
pause
exit /b 1

:find_python
set "PY="
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python314-arm64\python.exe"
    "%ProgramFiles%\Python314\python.exe"
    "%ProgramFiles%\Python314-arm64\python.exe"
) do (
    if not defined PY if exist "%%~P" set "PY=%%~P"
)
if defined PY exit /b 0
py -3.14 -c "import sys" >nul 2>&1
if errorlevel 1 exit /b 0
for /f "delims=" %%I in ('py -3.14 -c "import sys; print(sys.executable)"') do set "PY=%%I"
exit /b 0
