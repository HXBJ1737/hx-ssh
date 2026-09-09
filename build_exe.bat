@echo off
rem Build a single-file HxSSH.exe with PyInstaller. Output: dist\HxSSH.exe
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv not found. Please run run.bat once first.
  if not defined HXSSH_NO_PAUSE pause
  exit /b 1
)

rem Direct PyPI is blocked on some networks; use Tsinghua mirror.
set MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple

echo [1/3] Installing PyInstaller...
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check --timeout 120 --retries 10 -i %MIRROR% pyinstaller
if errorlevel 1 (
  echo [ERROR] pip install pyinstaller failed.
  if not defined HXSSH_NO_PAUSE pause
  exit /b 1
)

echo [2/3] Building exe, this may take a few minutes...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name HxSSH --icon "assets\icon.ico" --add-data "assets;assets" --hidden-import PySide6.QtCharts --exclude-module tkinter --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module tests main.py
if errorlevel 1 (
  echo [ERROR] PyInstaller build failed.
  if not defined HXSSH_NO_PAUSE pause
  exit /b 1
)

echo [3/3] Build OK. Output: %~dp0dist\HxSSH.exe
if not defined HXSSH_NO_PAUSE pause
