@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

set "TARGET=%~1"
if "%TARGET%"=="" goto NO_TARGET

if exist "%~dp0.venv\Scripts\python.exe" goto USE_VENV

where py.exe >nul 2>&1
if errorlevel 1 goto NO_PYTHON

py.exe -3 "%TARGET%"
set "RC=%ERRORLEVEL%"
goto FINISH

:USE_VENV
"%~dp0.venv\Scripts\python.exe" "%TARGET%"
set "RC=%ERRORLEVEL%"
goto FINISH

:NO_TARGET
echo [AstroSirilAssistant] No target Python file was specified.
pause
exit /b 2

:NO_PYTHON
echo [AstroSirilAssistant] Python 3 was not found.
pause
exit /b 3

:FINISH
if "%RC%"=="0" exit /b 0
echo [AstroSirilAssistant] Application error code: %RC%
pause
exit /b %RC%
