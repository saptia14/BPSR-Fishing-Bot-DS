@echo off
REM Build Doctor.exe and BPSR-Fishing.exe into dist\
cd /d "%~dp0"
python -m pip install -r requirements-dev.txt
python build.py %*
pause
