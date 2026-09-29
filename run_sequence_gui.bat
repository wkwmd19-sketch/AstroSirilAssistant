@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" sequence_gui.py
) else (
  py -3 sequence_gui.py
)
