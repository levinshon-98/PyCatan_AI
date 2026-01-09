@echo off
REM ============================================
REM PyCatan with AI Agents - FULL AUTO MODE
REM ============================================
REM AI plays completely autonomously!
REM No manual input needed - just watch!
REM ============================================

REM Enable DEBUG logging
set LOGLEVEL=DEBUG

echo.
echo ================================================================================
echo    PyCatan AI System - FULL AUTO MODE
echo ================================================================================
echo.
echo    AI will play completely autonomously - no manual input needed!
echo.
echo Starting components:
echo   1. AI Viewer (http://localhost:5001) - Shows AI prompts and responses
echo   2. LLM Logger - Shows real-time AI communication
echo   3. Catan Game with AI Agents (AUTO MODE)
echo.
echo ================================================================================
echo.

cd /d "%~dp0"

REM Check if Python is available
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found in PATH
    pause
    exit /b 1
)

REM Check for virtual environment
if exist ".venv\Scripts\python.exe" (
    set PYTHON_CMD=.venv\Scripts\python.exe
    echo [OK] Using virtual environment
) else (
    set PYTHON_CMD=python
    echo [!] No virtual environment found, using system Python
)

echo.

REM Start Web Viewer in a new window
echo [1/3] Starting AI Viewer...
start "AI Viewer - http://localhost:5001" cmd /k "%PYTHON_CMD% examples\ai_testing\web_viewer.py"

REM Wait for web viewer to start
timeout /t 2 /nobreak >nul

echo [OK] AI Viewer started at http://localhost:5001
echo.

REM Start LLM Logger Console in a new window
echo [2/3] Starting LLM Logger Console...
start "LLM Logger - Communication Log" cmd /k "%PYTHON_CMD% examples\ai_testing\llm_logger_console.py"
timeout /t 1 /nobreak >nul
echo [OK] LLM Logger console opened
echo.

REM Open browser for Unified View (combines game board and AI viewer)
echo [BROWSER] Opening Unified View...
timeout /t 1 /nobreak >nul
start http://localhost:5000/unified

echo.
echo [NOTE] Alternative views available:
echo    - http://localhost:5000         (Game board only)
echo    - http://localhost:5000/unified (Unified view - RECOMMENDED)
echo    - http://localhost:5001         (AI Viewer standalone)
echo.

echo.
echo [3/3] Starting game in AUTO mode...
echo.
echo ================================================================================
echo    FULL AUTO MODE - AI PLAYS AUTOMATICALLY
echo ================================================================================
echo    The AI agents will make all decisions automatically.
echo    Watch the LLM Logger window to see their thinking process.
echo    Press Ctrl+C to stop the game.
echo.
echo    Custom names: --names Alice Bob Charlie (also sets player count!)
echo    Examples:
echo      play_ai_auto.bat --names Dan Yael          (2 players)
echo      play_ai_auto.bat --names A B C D           (4 players)
echo ================================================================================
echo.

REM Start the game in AUTO mode
REM If no --names provided, use default 3 players
if "%~1"=="" (
    %PYTHON_CMD% examples\ai_testing\play_with_ai.py --auto --players 3 --all-ai
) else (
    %PYTHON_CMD% examples\ai_testing\play_with_ai.py --auto %*
)

echo.
echo ================================================================================
echo    Game session complete!
echo ================================================================================
echo.
echo Session logs saved to: examples\ai_testing\my_games\
echo.
pause
