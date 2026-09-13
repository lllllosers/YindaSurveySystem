@echo off
chcp 65001 >nul
setlocal

REM ============================================================
REM 引大入秦工程现状调查采集系统
REM V0.3.1 测试版一键构建脚本
REM ============================================================

cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"
set "SPEC=%~dp0YindaSurveySystem.spec"

set "BUILD_DIR=%~dp0build"
set "DIST_DIR=%~dp0dist"
set "DIST_APP=%~dp0dist\YindaSurveySystem"

set "RELEASE_NAME=引大入秦工程现状调查采集系统_V0.3.1_测试版"
set "RELEASE_ROOT=%~dp0release"
set "RELEASE_DIR=%RELEASE_ROOT%\%RELEASE_NAME%"

set "TEMPLATE_21=%~dp0templates\excel\form_2_1_V1.xlsx"
set "TEMPLATE_22=%~dp0templates\excel\form_2_2_V1.xlsx"
set "ICON_FILE=%~dp0assets\app_icon.ico"

echo.
echo ============================================================
echo   引大入秦工程现状调查采集系统
echo   V0.3.1 测试版构建
echo ============================================================
echo.

REM ============================================================
REM 1. 构建前检查
REM ============================================================

if not exist "%PYTHON%" (
    echo [ERROR] 未找到项目虚拟环境 Python：
    echo %PYTHON%
    goto :failed
)

if not exist "%SPEC%" (
    echo [ERROR] 未找到 PyInstaller 配置：
    echo %SPEC%
    goto :failed
)

if not exist "%ICON_FILE%" (
    echo [ERROR] 未找到程序图标：
    echo %ICON_FILE%
    goto :failed
)

if not exist "%TEMPLATE_21%" (
    echo [ERROR] 未找到附表2.1 Excel模板：
    echo %TEMPLATE_21%
    goto :failed
)

if not exist "%TEMPLATE_22%" (
    echo [ERROR] 未找到附表2.2 Excel模板：
    echo %TEMPLATE_22%
    goto :failed
)

echo [OK] 构建前资源检查通过。
echo.

REM ============================================================
REM 2. 清理旧构建结果
REM ============================================================

echo [1/5] 清理旧构建目录...

if exist "%BUILD_DIR%" (
    rmdir /s /q "%BUILD_DIR%"
)

if exist "%DIST_DIR%" (
    rmdir /s /q "%DIST_DIR%"
)

if exist "%RELEASE_DIR%" (
    rmdir /s /q "%RELEASE_DIR%"
)

echo [OK] 清理完成。
echo.

REM ============================================================
REM 3. PyInstaller 构建
REM ============================================================

echo [2/5] 正在执行 PyInstaller...

"%PYTHON%" -m PyInstaller --noconfirm --clean "%SPEC%"

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller 构建失败。
    goto :failed
)

if not exist "%DIST_APP%\YindaSurveySystem.exe" (
    echo.
    echo [ERROR] 构建结束后未找到：
    echo %DIST_APP%\YindaSurveySystem.exe
    goto :failed
)

echo [OK] PyInstaller 构建完成。
echo.

REM ============================================================
REM 4. 创建正式测试版交付目录
REM ============================================================

echo [3/5] 创建测试版交付目录...

if not exist "%RELEASE_ROOT%" (
    mkdir "%RELEASE_ROOT%"
)

mkdir "%RELEASE_DIR%"

xcopy /E /I /Y /Q "%DIST_APP%\*" "%RELEASE_DIR%\" >nul

if errorlevel 1 (
    echo [ERROR] 复制 PyInstaller 构建结果失败。
    goto :failed
)

echo [OK] 程序文件复制完成。
echo.

REM ============================================================
REM 5. 复制正式 Excel 模板
REM ============================================================

echo [4/5] 复制调查表 Excel 模板...

xcopy /E /I /Y /Q "%~dp0templates" "%RELEASE_DIR%\templates" >nul

if errorlevel 1 (
    echo [ERROR] Excel模板复制失败。
    goto :failed
)

echo [OK] Excel模板复制完成。
echo.

REM ============================================================
REM 6. 最终完整性检查
REM ============================================================

echo [5/5] 检查交付目录...

if not exist "%RELEASE_DIR%\YindaSurveySystem.exe" (
    echo [ERROR] 缺少主程序。
    goto :failed
)

if not exist "%RELEASE_DIR%\_internal" (
    echo [ERROR] 缺少 _internal 运行依赖目录。
    goto :failed
)

if not exist "%RELEASE_DIR%\templates\excel\form_2_1_V1.xlsx" (
    echo [ERROR] 缺少附表2.1 Excel模板。
    goto :failed
)

if not exist "%RELEASE_DIR%\templates\excel\form_2_2_V1.xlsx" (
    echo [ERROR] 缺少附表2.2 Excel模板。
    goto :failed
)

if exist "%RELEASE_DIR%\local_data" (
    echo [ERROR] 交付目录中意外存在 local_data。
    echo 为防止测试数据库被带入交付包，构建已停止。
    goto :failed
)

echo.
echo ============================================================
echo [SUCCESS] 测试版构建完成
echo.
echo 输出目录：
echo %RELEASE_DIR%
echo.
echo 当前交付目录不包含 local_data。
echo 请完成最终冒烟测试后，再添加使用说明并压缩交付。
echo ============================================================
echo.

pause
exit /b 0


:failed
echo.
echo ============================================================
echo [FAILED] 测试版构建失败
echo 请根据上方错误信息检查后重新执行。
echo ============================================================
echo.
pause
exit /b 1