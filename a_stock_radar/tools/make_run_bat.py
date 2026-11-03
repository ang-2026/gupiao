# -*- coding: utf-8 -*-
"""生成 run.bat（纯 ASCII + CRLF，避免 Windows 命令行中文编码问题）。"""
from pathlib import Path

BAT = r"""@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo [ERROR] .venv not found.
  echo Please read README.md section 2 to install dependencies.
  echo.
  pause
  exit /b 1
)

set "KIVY_HOME=%~dp0.tools\kivyhome"
set "STOCKLENS_HOME=%~dp0data"
set "KIVY_NO_ARGS=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

".venv\Scripts\python.exe" "tools\launch.py"

if errorlevel 1 (
  echo.
  echo [ERROR] The app exited unexpectedly. See messages above.
  pause
)
"""

target = Path(__file__).resolve().parent.parent / "run.bat"
target.write_bytes(BAT.replace("\n", "\r\n").encode("ascii"))
print("wrote", target, target.stat().st_size, "bytes")
