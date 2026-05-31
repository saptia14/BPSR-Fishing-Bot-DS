@echo off
REM Launch the fishing bot elevated. Required when the game runs as Administrator,
REM otherwise Windows silently ignores the bot's simulated input (UIPI).
cd /d "%~dp0"
powershell -Command "Start-Process -FilePath 'python' -ArgumentList 'main.py' -Verb RunAs"
