@echo off
set "ROOT=%~dp0"
echo [1/3] Checking database structure...
cd /d "%ROOT%backend"
"%ROOT%backend\.venv\Scripts\python.exe" -m alembic upgrade head
if errorlevel 1 (
  echo Database upgrade failed. Please keep this window open and contact the system administrator.
  pause
  exit /b 1
)
echo [2/3] Starting API service...
start "Yinda Web Backend" cmd /k ""%ROOT%backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --app-dir "%ROOT%backend""
timeout /t 2 /nobreak >nul
echo [3/3] Starting Web service...
start "Yinda Web Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev"
echo.
echo Yinda Web Center development services started.
echo Frontend: http://127.0.0.1:8848
echo API docs: http://127.0.0.1:8000/docs
echo.
