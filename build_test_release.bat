@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Project virtual environment Python was not found:
    echo %PYTHON%
    pause
    exit /b 1
)

"%PYTHON%" "%~dp0build_test_release.py"

set "EXIT_CODE=%ERRORLEVEL%"

echo.

if not "%EXIT_CODE%"=="0" (
    echo [FAILED] Test release build failed.
    echo Review the error above and run again.
) else (
    echo [SUCCESS] Test release build finished.
)

echo.
pause
exit /b %EXIT_CODE%
