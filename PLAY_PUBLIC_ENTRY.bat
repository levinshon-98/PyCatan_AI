@echo off
setlocal

REM PyCatan AI - Public single-page entrypoint
REM
REM Usage:
REM   PLAY_PUBLIC_ENTRY.bat
REM   PLAY_PUBLIC_ENTRY.bat --use-env-keys
REM   PLAY_PUBLIC_ENTRY.bat --port 7860 --use-env-keys

echo ===============================================================
echo    PyCatan AI - Public Entry
echo ===============================================================
echo.
echo This opens a guest-friendly browser page with:
echo   - New game
echo   - Analysed replay library
echo   - Replay availability admin panel
echo.

set PYTHON_CMD=python
%PYTHON_CMD% --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not available on PATH.
    echo Install Python 3.10+ or activate the project virtualenv.
    pause
    exit /b 1
)

echo Starting public entrypoint...
%PYTHON_CMD% examples\ai_testing\play_public_entry.py %*

echo.
echo Public entry session complete.
pause
