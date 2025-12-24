@echo off
REM Activate virtual environment and run the Catan game
call .venv\Scripts\activate.bat
python play_catan.py
pause
