@echo off
setlocal EnableExtensions
chcp 65001 >nul

cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"
set "SPEC=%~dp0YindaSurveySystem.spec"

set "BUILD_DIR=%~dp0build"
set "DIST_DIR=%~dp0dist"
set "DIST_APP=%~dp0dist\YindaSurveySystem"

set "RELEASE_ROOT=%~dp0release"
set "TEMPLATE_DIR=%~dp0templates\excel"
set "ICON_FILE=%~dp0assets\app_icon.ico"

REM ============================================================
REM 1. Preflight
REM ============================================================

if not exist "%PYTHON%" (
    echo [ERROR] Project virtualenv Python was not found:
    echo %PYTHON%
    goto :failed
)

if not exist "%~dp0src\version.py" (
    echo [ERROR] src\version.py was not found.
    goto :failed
)

REM Read APP_VERSION / APP_STAGE directly from version.py.
REM This avoids nested FOR/F command quoting around python.exe.
set "APP_VERSION="
set "APP_STAGE="

for /f "tokens=1,2 delims== " %%A in (src\version.py) do (
    if "%%A"=="APP_VERSION" set "APP_VERSION=%%~B"
    if "%%A"=="APP_STAGE" set "APP_STAGE=%%~B"
)

if not defined APP_VERSION (
    echo [ERROR] Could not read APP_VERSION from src\version.py.
    goto :failed
)

if not defined APP_STAGE (
    echo [ERROR] Could not read APP_STAGE from src\version.py.
    goto :failed
)

REM Keep the build folder name ASCII-only for cmd/xcopy robustness.
set "RELEASE_NAME=YindaSurveySystem_V%APP_VERSION%_test"
set "RELEASE_DIR=%RELEASE_ROOT%\%RELEASE_NAME%"

echo.
echo ============================================================
echo   Yinda Survey System
echo   Version: %APP_VERSION%
echo   Stage:   %APP_STAGE%
echo ============================================================
echo.

if not exist "%SPEC%" (
    echo [ERROR] PyInstaller spec was not found:
    echo %SPEC%
    goto :failed
)

if not exist "%ICON_FILE%" (
    echo [ERROR] Application icon was not found:
    echo %ICON_FILE%
    goto :failed
)

if not exist "%TEMPLATE_DIR%" (
    echo [ERROR] Excel template directory was not found:
    echo %TEMPLATE_DIR%
    goto :failed
)

echo [OK] Preflight passed.
echo.

REM ============================================================
REM 2. Clean old build results
REM ============================================================

echo [1/5] Cleaning old build directories...

if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"

echo [OK] Clean complete.
echo.

REM ============================================================
REM 3. PyInstaller
REM ============================================================

echo [2/5] Running PyInstaller...

"%PYTHON%" -m PyInstaller --noconfirm --clean "%SPEC%"

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller failed.
    goto :failed
)

if not exist "%DIST_APP%\YindaSurveySystem.exe" (
    echo.
    echo [ERROR] Executable was not produced:
    echo %DIST_APP%\YindaSurveySystem.exe
    goto :failed
)

echo [OK] PyInstaller complete.
echo.

REM ============================================================
REM 4. Create release directory
REM ============================================================

echo [3/5] Creating release directory...

if not exist "%RELEASE_ROOT%" mkdir "%RELEASE_ROOT%"
mkdir "%RELEASE_DIR%"

xcopy /E /I /Y /Q "%DIST_APP%\*" "%RELEASE_DIR%\" >nul

if errorlevel 1 (
    echo [ERROR] Failed to copy PyInstaller output.
    goto :failed
)

echo [OK] Program files copied.
echo.

REM ============================================================
REM 5. Copy Excel templates
REM ============================================================

echo [4/5] Copying Excel templates...

xcopy /E /I /Y /Q "%~dp0templates" "%RELEASE_DIR%\templates" >nul

if errorlevel 1 (
    echo [ERROR] Failed to copy Excel templates.
    goto :failed
)

echo [OK] Templates copied.
echo.

REM ============================================================
REM 6. Integrity checks
REM ============================================================

echo [5/5] Checking release directory...

if not exist "%RELEASE_DIR%\YindaSurveySystem.exe" (
    echo [ERROR] Main executable is missing.
    goto :failed
)

if not exist "%RELEASE_DIR%\_internal" (
    echo [ERROR] _internal runtime directory is missing.
    goto :failed
)

if not exist "%RELEASE_DIR%\templates\excel" (
    echo [ERROR] Excel template directory is missing.
    goto :failed
)

if exist "%RELEASE_DIR%\local_data" (
    echo [ERROR] local_data unexpectedly exists in the release directory.
    echo [ERROR] Build stopped to avoid shipping a test database.
    goto :failed
)

echo.
echo ============================================================
echo [SUCCESS] Test build completed.
echo Release directory:
echo %RELEASE_DIR%
echo ============================================================
echo.
pause
exit /b 0

:failed
echo.
echo ============================================================
echo [FAILED] Test build failed.
echo Review the error above and run the script again.
echo ============================================================
echo.
pause
exit /b 1
