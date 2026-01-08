@echo off
REM ================================================================================
REM PyCatan AI System - UPDATED VERSION
REM ================================================================================
REM This script has been updated to use the new AI system.
REM Old files moved to: examples\ai_testing\_deprecated\
REM ================================================================================

echo.
echo ================================================================================
echo    PyCatan AI System
echo ================================================================================
echo.
echo Starting components:
echo   1. AI Viewer (http://localhost:5001) - Shows AI prompts and responses
echo   2. Catan Game with AI Agents (manual input mode)
echo.
echo ================================================================================
echo.

cd /d "%~dp0"

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
echo [1/2] Starting AI Viewer...
start "AI Viewer - http://localhost:5001" cmd /k "%PYTHON_CMD% examples\ai_testing\web_viewer.py"

REM Wait for web viewer to start
timeout /t 2 /nobreak >nul

echo [OK] AI Viewer started at http://localhost:5001
echo.

REM Open browser for AI Viewer
echo [BROWSER] Opening AI Viewer...
timeout /t 2 /nobreak >nul
start http://localhost:5001

echo.
echo [2/2] Starting game...
echo.
echo ================================================================================
echo    MANUAL AI MODE
echo ================================================================================
echo    When it's an AI player's turn:
echo    - A prompt is generated and saved
echo    - You enter the action the AI should take
echo.
echo    Commands: r (roll), e (end turn), s 14 (settlement), rd 14 15 (road)
echo    Type 'help' for full list
echo ================================================================================
echo.

REM Start the game with the new system
%PYTHON_CMD% examples\ai_testing\play_with_ai.py

echo.
echo ================================================================================
echo    Session Complete!
echo ================================================================================
echo Session logs: examples\ai_testing\my_games\
echo.
pause
