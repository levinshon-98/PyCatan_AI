@echo off
REM ============================================
REM PyCatan with AI Agents - Better UX Mode
REM ============================================
REM Opens a single-page setup app for:
REM   - New live OpenRouter game
REM   - Resume an existing recorded session and continue live
REM   - Watch and analyse any existing session from a session library
REM ============================================

set LOGLEVEL=DEBUG

echo.
echo ================================================================================
echo    PyCatan AI System - PLAY_WITH_BETTER_UX
echo ================================================================================
echo.
echo Starting components:
echo   1. AI Viewer (http://localhost:5001) - Shows AI prompts and responses
echo   2. LLM Logger - Shows real-time AI communication
echo   3. Better UX browser page - Run game or replay library
echo   4. Catan Game with AI Agents
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

echo [3/3] Opening Better UX page and starting game after submit...
echo.
echo ================================================================================
echo    PLAY_WITH_BETTER_UX
echo ================================================================================
echo    The browser page has two main routes:
echo      - Run game: new game or resume from an existing session
echo      - Watch/analyse session: searchable session library with preview and back button
echo    Live runs use OpenRouter models and Gemini TTS by default.
echo    Reactions default to async parallel mode.
echo    Press Ctrl+C here to stop the game.
echo ================================================================================
echo.

%PYTHON_CMD% examples\ai_testing\play_with_better_ux.py %*

echo.
echo ================================================================================
echo    Game session complete!
echo ================================================================================
echo.
echo Session logs saved to: examples\ai_testing\my_games\
echo.
pause
