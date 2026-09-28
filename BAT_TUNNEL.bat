@echo off
setlocal EnableDelayedExpansion
set "WG=%~dp0"
if "%WG:~-1%"=="\" set "WG=%WG:~0,-1%"
set "CF=C:\Program Files (x86)\cloudflared\cloudflared.exe"
set "PORT=8029"

echo ==== KIEM TRA server game 8029 ====
set "SRVP="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":8029 .*LISTENING"') do set "SRVP=%%p"
if defined SRVP goto :co_server
echo  [LOI] Server 8029 chua chay. Mo KHOIDONG_TOAN_BO.bat truoc.
pause
exit /b 1

:co_server
echo  Server 8029 dang chay (PID !SRVP!^).

echo ==== BAT tunnel internet (Cloudflare quick tunnel) ====
set "TUNP="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":20241 .*LISTENING"') do set "TUNP=%%p"

if defined TUNP (
  echo  Tunnel da chay, doc lai link cu trong tunnel.log.
  goto :trich_link
)
del /q "%WG%\tunnel.log" 2>nul
start "busidol-tunnel" /min "%CF%" tunnel --url http://localhost:%PORT% --logfile "%WG%\tunnel.log"
echo  Dang cho Cloudflare cap link (toi da 30 giay^)...
timeout /t 16 /nobreak >nul

:trich_link
echo ==== TRICH LINK CHIA SE ====
set "URL="
for /f "usebackq delims=" %%l in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%WG%\get_tunnel_url.ps1"`) do set "URL=%%l"

if not defined URL goto :chua_co_link
set "URI=%URL%/ELDORADO_WEB/login_page.php"
set "URI2=%URL%/source_20240722/index__mobile.html#sign=offline&time=0"
echo.
echo ============ LINK CHO BAN BE ============
echo  Login : %URI%
echo.
echo  Luu y: link doi moi lan bat tunnel. Gui link tren cho ban be.
echo.
start "" "%URI%"
pause
exit /b 0

:chua_co_link
echo  Chua thay link trong tunnel.log. Mo file tunnel.log xem chi tiet, hoac doi vai giay roi bam lai.
pause