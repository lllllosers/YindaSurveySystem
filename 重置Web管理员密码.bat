@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0web_center\backend"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Web 后端虚拟环境不存在。
  pause
  exit /b 1
)

echo.
echo 引大调查数据中心 - 管理员密码重置
echo 密码输入时不会在屏幕上显示字符，这是正常的安全保护。
echo.
".venv\Scripts\python.exe" -m app.cli.reset_admin_password
echo.
pause
endlocal
