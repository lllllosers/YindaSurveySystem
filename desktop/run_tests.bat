@echo off
chcp 65001 >nul
cd /d "%~dp0"

title 引大灌区调查数据采集系统 - 自动化测试

echo.
echo ============================================================
echo 引大灌区调查数据采集系统
echo 自动化回归测试
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] 未找到项目虚拟环境：
    echo %CD%\.venv\Scripts\python.exe
    echo.
    echo 请确认当前目录中的 .venv 已正确创建。
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" "run_tests.py"

set TEST_EXIT_CODE=%ERRORLEVEL%

echo.

if "%TEST_EXIT_CODE%"=="0" (
    echo ============================================================
    echo [PASS] 全部自动化测试通过
    echo ============================================================
) else (
    echo ============================================================
    echo [FAIL] 自动化测试未通过
    echo 请查看 test_logs 目录中的最新日志。
    echo ============================================================
)

echo.
pause

exit /b %TEST_EXIT_CODE%