@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "LAUNCHER_PY=web_center\backend\.venv\Scripts\pythonw.exe"
if not exist "%LAUNCHER_PY%" (
  echo.
  echo [ERROR] Web 后端虚拟环境不存在。
  echo 请先完成 web_center\backend\.venv 环境配置。
  echo.
  pause
  exit /b 1
)

start "Yinda Web Center" "%LAUNCHER_PY%" "web_center\launcher.py"
endlocal
