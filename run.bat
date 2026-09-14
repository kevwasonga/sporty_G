@echo off
echo ============================================
echo   Sporty OTP Lab - Windows launcher
echo ============================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ** Python not found.  This tool needs Python 3.10+.
    echo    Download it from https://www.python.org/downloads/ and
    echo    make sure "Add python.exe to PATH" is ticked during install.
    echo.
    pause
    exit /b 1
)

python run.py %*
if %errorlevel% neq 0 (
    echo.
    echo ** run.py exited with an error.  Scroll up to see what happened.
    echo.
)
pause