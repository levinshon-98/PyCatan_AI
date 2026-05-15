@echo off
REM ============================================
REM PyCatan with AI Agents - Browser Settings Mode
REM ============================================
REM Opens a setup page where the user chooses:
REM   - Gemini model
REM   - Gemini API key
REM   - Player count and names
REM Then starts the same full-auto AI game flow.
REM ============================================

set LOGLEVEL=DEBUG

echo.
echo ================================================================================
echo    PyCatan AI System - PLAY_WITH_SET_SETTINGS
echo ================================================================================
echo.
echo Starting components:
echo   1. AI Viewer (http://localhost:5001) - Shows AI prompts and responses
echo   2. LLM Logger - Shows real-time AI communication
echo   3. Browser setup page - Gemini model, API key, players
echo   4. Catan Game with AI Agents (AUTO MODE)
echo.
echo ================================================================================
echo.

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

echo.

echo [1/3] Starting AI Viewer...
start "AI Viewer - http://localhost:5001" cmd /k "%PYTHON_CMD% examples\ai_testing\web_viewer.py"
timeout /t 2 /nobreak >nul
echo [OK] AI Viewer started at http://localhost:5001
echo.

echo [2/3] Starting LLM Logger Console...
start "LLM Logger - Communication Log" cmd /k "%PYTHON_CMD% examples\ai_testing\llm_logger_console.py"
timeout /t 1 /nobreak >nul
echo [OK] LLM Logger console opened
echo.

echo [3/3] Opening browser setup and starting game after submit...
echo.
echo ================================================================================
echo    PLAY_WITH_SET_SETTINGS
echo ================================================================================
echo    A browser page will ask for Gemini model, API key, player count, and names.
echo    After you submit, the board will load automatically in that same tab.
echo    Press Ctrl+C here to stop the game.
echo ================================================================================
echo.

%PYTHON_CMD% examples\ai_testing\play_with_ai.py --auto --browser-settings %*

echo.
echo ================================================================================
echo    Game session complete!
echo ================================================================================
echo.
echo Session logs saved to: examples\ai_testing\my_games\
echo.
pause
