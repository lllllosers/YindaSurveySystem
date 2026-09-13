@echo off
setlocal

REM 切换到本批处理文件所在的项目根目录
cd /d "%~dp0"

REM 项目虚拟环境 Python
set "PYTHON=%~dp0.venv\Scripts\python.exe"

REM 程序入口
set "APP=%~dp0src\main.py"

REM 检查虚拟环境
if not exist "%PYTHON%" (
    echo.
    echo [启动失败] 未找到项目虚拟环境：
    echo %PYTHON%
    echo.
    echo 请确认 .venv 已正确创建。
    pause
    exit /b 1
)

REM 检查程序入口
if not exist "%APP%" (
    echo.
    echo [启动失败] 未找到程序入口：
    echo %APP%
    echo.
    pause
    exit /b 1
)

REM 启动 PySide6 程序，不显示命令行窗口
start "" "%PYTHON%" "%APP%"

endlocal