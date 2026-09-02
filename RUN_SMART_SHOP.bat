@echo off
cd /d "%~dp0"
echo.
echo ==========================================
echo        SMART SHOP AI - STARTING
 echo ==========================================
echo.
start "Smart Shop AI Browser" http://127.0.0.1:5000/
python app.py
pause
