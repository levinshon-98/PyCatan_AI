@echo off
REM ============================================
REM PyCatan with AI Agents - Full System Launcher
REM ============================================
REM This script starts:
REM   1. Web Viewer (for viewing AI prompts/responses)
REM   2. The main game with AI agents
REM ============================================

REM Enable DEBUG logging
set LOGLEVEL=DEBUG

echo.
echo ================================================================================
echo    PyCatan AI System - Full Launch
echo ================================================================================
echo.
echo Starting components:
echo   1. AI Viewer (http://localhost:5001) - Shows AI prompts and responses
echo   2. Catan Game with AI Agents
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

REM Open browser for AI Viewer
echo [BROWSER] Opening AI Viewer...
timeout /t 1 /nobreak >nul
start http://localhost:5001

echo.
echo [3/3] Starting game in this window...
echo.
echo ================================================================================
echo    GAME CONTROLS
echo ================================================================================
echo    - LLM sends suggestions, you approve or override
echo    - Press ENTER to accept LLM suggestion
echo    - Or type your own command
echo.
echo    Quick commands:
echo      r          - Roll dice
echo      e          - End turn
echo      s 14       - Build settlement at node 14
echo      rd 14 15   - Build road from 14 to 15
echo.
echo    Flags:
echo      --no-llm   - Don't send to LLM (offline mode)
echo      --auto     - Let AI play automatically
echo ================================================================================
echo.

REM Start the game
%PYTHON_CMD% examples\ai_testing\play_with_ai.py %*

echo.
echo ================================================================================
echo    Game session complete!
echo ================================================================================
echo.
echo Session logs saved to: examples\ai_testing\my_games\
echo.
pause
