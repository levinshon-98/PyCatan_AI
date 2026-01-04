@echo off
REM Start AI Tester, Web Viewer, and Game in parallel

echo ================================================================================
echo 🎮 Starting AI Catan System
echo ================================================================================
echo.
echo Opening THREE windows + TWO browser tabs:
echo   1. AI Tester (monitoring AI responses)
echo   2. AI Viewer (http://localhost:5001) - Shows AI thinking/responses
echo   3. Catan Game (the actual game)
echo   + Game Board (http://localhost:5000) - Shows the Catan board
echo.
echo ================================================================================
echo.

REM Start AI Tester in a new window
start "AI Tester - Monitoring" cmd /k ".venv\Scripts\python.exe examples\ai_testing\test_ai_live.py"

REM Wait a moment for AI tester to initialize
timeout /t 2 /nobreak >nul

echo ✅ AI Tester started in separate window
echo.

REM Start Web Viewer in a new window
start "AI Viewer - http://localhost:5001" cmd /k ".venv\Scripts\python.exe examples\ai_testing\web_viewer.py"

timeout /t 2 /nobreak >nul

echo ✅ AI Viewer started at http://localhost:5001
echo.
echo 🌐 Opening AI Viewer in browser...
timeout /t 3 /nobreak >nul
start http://localhost:5001
echo.
echo Starting game in this window...
echo   (Game board will open at http://localhost:5000)
echo.

REM Start the game in this window
.venv\Scripts\python.exe examples\ai_testing\play_with_prompts.py

pause
