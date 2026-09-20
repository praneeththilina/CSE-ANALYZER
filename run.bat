@echo off
title CSE Stock Analyzer
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    start "" "venv\Scripts\pythonw.exe" main.py
) else (
    echo Virtual environment not found. Running with system python...
    start "" python main.py
)
