@echo off
setlocal
set "ADMIN_PORT=8030"
set "ADMIN_URL=http://127.0.0.1:%ADMIN_PORT%/admin-control"

for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":%ADMIN_PORT% .*LISTENING"') do set "ADMIN_PID=%%p"

if not defined ADMIN_PID (
  echo [LOI] Admin chua chay tren cong %ADMIN_PORT%.
  echo Hay chay KHOIDONG_TOAN_BO.bat truoc.
  pause
  exit /b 1
)

start "" "%ADMIN_URL%"
endlocal
