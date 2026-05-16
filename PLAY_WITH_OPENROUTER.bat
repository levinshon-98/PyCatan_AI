@echo off
REM ============================================
REM PyCatan with AI Agents - OpenRouter Settings Mode
REM ============================================
REM Opens a setup page where the user chooses:
REM   - Run mode and replay/analyse options
REM   - OpenRouter model per AI player
REM   - API key mode: environment keys or typed keys
REM   - TTS provider/settings
REM   - Reaction mode and table-talk language
REM Then starts the same full-auto AI game flow.
REM ============================================

set LOGLEVEL=DEBUG

echo.
echo ================================================================================
echo    PyCatan AI System - PLAY_WITH_OPENROUTER
echo ================================================================================
echo.
echo Starting components:
echo   1. AI Viewer (http://localhost:5001) - Shows AI prompts and responses
echo   2. LLM Logger - Shows real-time AI communication
echo   3. Browser setup page - OpenRouter per-agent model selection
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

echo [3/3] Opening OpenRouter setup and starting game after submit...
echo.
echo ================================================================================
echo    PLAY_WITH_OPENROUTER
echo ================================================================================
echo    A browser page will ask for run mode, replay/session options, players,
echo    per-agent OpenRouter models, TTS, reactions, and keys.
echo    Default key mode: use OPENROUTER_API_KEY / TTS keys from ENV or .env when blank.
echo    Force typed keys: add --ask-api-keys
echo    Explicit ENV mode: add --use-env-keys
echo    Press Ctrl+C here to stop the game.
echo ================================================================================
echo.

%PYTHON_CMD% examples\ai_testing\play_with_openrouter.py %*

echo.
echo ================================================================================
echo    Game session complete!
echo ================================================================================
echo.
echo Session logs saved to: examples\ai_testing\my_games\
echo.
pause
