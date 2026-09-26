@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "LAUNCHER_PY=web_center\backend\.venv\Scripts\pythonw.exe"
if not exist "%LAUNCHER_PY%" (
  echo.
  echo 启动失败：系统运行环境尚未准备好。
  echo 请联系系统管理员完成首次安装配置。
  echo.
  pause
  exit /b 1
)

start "Yinda Web Center" "%LAUNCHER_PY%" "web_center\launcher.py"
endlocal
