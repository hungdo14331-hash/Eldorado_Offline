@echo off
setlocal
cd /d "%~dp0.."
python character_workshop\build_characters.py
if errorlevel 1 (
  echo.
  echo Build nhan vat THAT BAI.
  pause
  exit /b 1
)
echo.
echo Build nhan vat THANH CONG.
pause
