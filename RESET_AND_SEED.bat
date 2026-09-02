@echo off
cd /d "%~dp0"
echo Resetting the demo product catalogue...
python seed_shop.py
echo.
echo Catalogue reset complete. Starting Smart Shop AI...
python app.py
pause
