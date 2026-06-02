@echo off
cd /d "%~dp0"
python -c "import customtkinter" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    python -m pip install -r requirements.txt
)
python autoclicker.py
