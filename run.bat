@echo off
setlocal enabledelayedexpansion
echo ============================================
echo   Sporty OTP Lab - Windows launcher
echo ============================================
echo.

set "PYCMD="

rem Prefer the official "py" launcher (cleanest on Windows).
where py >nul 2>nul
if "!errorlevel!"=="0" set "PYCMD=py -3"

rem Fall back to a plain python in PATH.
if "!PYCMD!"=="" where python >nul 2>nul
if "!errorlevel!"=="0" if "!PYCMD!"=="" set "PYCMD=python"

if "!PYCMD!"=="" (
    echo ** Python 3.10+ was not found.
    echo    Install it from https://www.python.org/downloads/
    echo    and tick "Add python.exe to PATH" during setup.
    echo    Then close this window and run run.bat again.
    echo.
    pause
    exit /b 1
)

rem Verify it actually runs (catches the Microsoft Store stub / broken PATH).
%PYCMD% --version
if "!errorlevel!" neq "0" (
    echo.
    echo ** Python is present but does not run. This usually means it is the
    echo    Microsoft Store shortcut. Install the real Python from
    echo    https://www.python.org/downloads/ instead, then close and
    echo    reopen this window.
    echo.
    pause
    exit /b 1
)

%PYCMD% run.py %*
if "!errorlevel!" neq "0" (
    echo.
    echo ** run.py exited with an error. Scroll up to see what happened.
    echo.
)
pause