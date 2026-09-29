@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

set "TARGET=%~dp0gui.py"

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

:NO_PYTHON
echo.
echo [AstroSirilAssistant] Python 3 was not found.
echo Run install_windows.bat first or install Python 3.
echo.
pause
exit /b 3

:FINISH
if "%RC%"=="0" exit /b 0

echo.
echo [AstroSirilAssistant] The application exited with error code %RC%.
echo Check the error message above.
echo.
pause
exit /b %RC%
