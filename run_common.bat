@echo off
setlocal
cd /d "%~dp0"

set "TARGET=%~1"
if "%TARGET%"=="" (
  echo [AstroSirilAssistant] 실행할 Python 파일이 지정되지 않았습니다.
  pause
  exit /b 2
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "%TARGET%"
  set "RC=%ERRORLEVEL%"
) else (
  where py >nul 2>&1
  if errorlevel 1 (
    echo [AstroSirilAssistant] Python launcher ^(py^)를 찾지 못했습니다.
    echo .venv를 생성하거나 Python 3를 설치해주세요.
    pause
    exit /b 3
  )
  py -3 "%TARGET%"
  set "RC=%ERRORLEVEL%"
)

if not "%RC%"=="0" (
  echo.
  echo [AstroSirilAssistant] 프로그램이 오류 코드 %RC%로 종료되었습니다.
  echo 위 오류 메시지를 확인해주세요.
  pause
)

exit /b %RC%
