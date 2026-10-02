@echo off
setlocal
set "ROOT=%~dp0"
python --version >nul 2>&1
if errorlevel 1 (
  echo Python is not available. Install Python and make it available to this terminal.
  exit /b 1
)
if not exist "%ROOT%.venv" (
  echo Creating Desktop virtual environment...
  python -m venv "%ROOT%.venv"
  if errorlevel 1 goto failed
)
if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo Desktop .venv is incomplete. Check the existing environment before retrying.
  exit /b 1
)
echo Installing Desktop development dependencies...
"%ROOT%.venv\Scripts\python.exe" -m pip install -r "%ROOT%requirements-dev.txt"
if errorlevel 1 goto failed
echo Installing the local Windows ICU startup hook...
copy /y "%ROOT%dev\sitecustomize.py" "%ROOT%.venv\Lib\site-packages\sitecustomize.py" >nul
if errorlevel 1 goto failed
"%ROOT%.venv\Scripts\python.exe" -I -c "from PySide6 import QtCore, QtGui, QtWidgets; print(QtCore.qVersion())"
if errorlevel 1 goto failed
echo Desktop development environment is ready.
exit /b 0

:failed
echo Desktop development environment setup failed. See the error above.
exit /b 1
