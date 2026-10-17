@echo off
cd /d "%~dp0"
".venv-patched\Scripts\python.exe" "scripts\review_train.py"
if errorlevel 1 pause
