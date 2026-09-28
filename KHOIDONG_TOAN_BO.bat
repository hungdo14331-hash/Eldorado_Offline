@echo off
setlocal
set "WG=%~dp0"
if "%WG:~-1%"=="\" set "WG=%WG:~0,-1%"
set "PY=C:\Users\THE HUAN\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%PY%" set "PY=python"
set "PORT=8029"
set "ADMINPORT=8030"
set "BUSIDOL_ADMIN_PASSWORD=001207027653"

echo ==== Mat khau admin da dat theo launcher ====

echo ==== DUNG server cu (neu con chay) ====
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT% :%ADMINPORT%" ^| findstr LISTENING') do (
   echo  Dang tat PID %%p ...
   taskkill /f /pid %%p >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo ==== KHOI DONG server offline ====
start "busidol-offline" /min "%PY%" "%WG%\serve.py" --mode offline --port %PORT% --admin-port %ADMINPORT% --db "%WG%\busidol.db" --require-login
timeout /t 3 /nobreak >nul

echo ==== XAC NHAN ====
netstat -ano | findstr ":%PORT% :%ADMINPORT%"
echo.
echo Server dang chay.
echo  - Game:  http://127.0.0.1:%PORT%
echo  - Admin: http://127.0.0.1:%ADMINPORT%/admin-control
pause
