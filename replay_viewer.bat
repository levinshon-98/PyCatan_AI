@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
cd /d "%ROOT%"

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=python"
) else (
    set "PYTHON_CMD=py -3"
)

if "%~1"=="" (
    %PYTHON_CMD% examples\ai_testing\replay_viewer.py --port 5050
    goto :done
)

set "FIRST_ARG=%~1"
if "%FIRST_ARG:~0,2%"=="--" (
    %PYTHON_CMD% examples\ai_testing\replay_viewer.py %*
    goto :done
)

set "SESSION=%~1"
set "REST_ARGS="

:collect_args
shift
if "%~1"=="" goto :run_session
set "REST_ARGS=!REST_ARGS! "%~1""
goto :collect_args

:run_session
%PYTHON_CMD% examples\ai_testing\replay_viewer.py --session "%SESSION%" !REST_ARGS!

:done
endlocal
