@echo off
REM ============================================
REM PyCatan AI Game Analysis Replay
REM ============================================
REM Opens a recorded session as a visual replay with
REM per-decision analysis: memory, prompt context, tools,
REM thinking, communication, action, and engine result.
REM ============================================

cd /d "%~dp0"

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found in PATH
    pause
    exit /b 1
)

if exist ".venv\Scripts\python.exe" (
    set PYTHON_CMD=.venv\Scripts\python.exe
    echo [OK] Using virtual environment
) else (
    set PYTHON_CMD=python
    echo [!] No virtual environment found, using system Python
)

set HAS_SESSION=0
set NORMALIZED_ARGS=

:parse_args
if "%~1"=="" goto after_parse
if /I "%~1"=="--session" (
    if "%~2"=="" (
        echo ERROR: --session requires a session name or path.
        pause
        exit /b 1
    )
    set HAS_SESSION=1
    set NORMALIZED_ARGS=%NORMALIZED_ARGS% --replay-session "%~2"
    shift
    shift
    goto parse_args
)
if /I "%~1"=="--replay-session" set HAS_SESSION=1
if /I "%~1"=="--resume-session" set HAS_SESSION=1
set NORMALIZED_ARGS=%NORMALIZED_ARGS% %1
shift
goto parse_args

:after_parse
if "%HAS_SESSION%"=="0" (
    echo.
    echo Usage:
    echo   ANALYSE_GAME.bat --session session_YYYYMMDD_HHMMSS
    echo.
    echo You can also pass any replay options, for example:
    echo   ANALYSE_GAME.bat --session session_20260516_000342 --replay-delay 1.5
    echo.
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo    ANALYSE GAME - VISUAL REPLAY WITH DECISION TRACE
echo ================================================================================
echo.
echo The browser will open when the replay timeline is ready.
echo Use Play/Pause or the slider, then click Analyse to inspect the current decision.
echo.

%PYTHON_CMD% examples\ai_testing\play_with_ai.py --auto --analyse-game %NORMALIZED_ARGS%

echo.
pause
