@echo off
set "ROOT=%~dp0"
start "Yinda Web Backend" cmd /k ""%ROOT%backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --app-dir "%ROOT%backend""
timeout /t 2 /nobreak >nul
start "Yinda Web Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev"
echo.
echo Yinda Web Center development services started.
echo Frontend: http://127.0.0.1:8848
echo API docs: http://127.0.0.1:8000/docs
echo.
