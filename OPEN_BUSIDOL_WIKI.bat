@echo off
setlocal

title BUSIDOL Wiki Launcher

REM ============================================================
REM BUSIDOL Wiki - Quick Launcher
REM Dat file BAT nay o thu muc goc cua project:
REM E:\UserData\Desktop\TEST ELDORADO\busidol_offline
REM ============================================================

cd /d "%~dp0"

set "PORT=8080"
set "WIKI_URL=http://localhost:%PORT%/wiki/"

echo.
echo ============================================
echo   BUSIDOL WIKI - QUICK LAUNCHER
echo ============================================
echo.
echo Project folder:
echo %CD%
echo.
echo Dang kiem tra Python...

where python >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=python"
    goto :START_SERVER
)

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py"
    goto :START_SERVER
)

echo.
echo [LOI] Khong tim thay Python.
echo Hay cai Python va dam bao python hoac py co trong PATH.
echo.
pause
exit /b 1


:START_SERVER
echo Tim thay Python: %PYTHON_CMD%
echo.
echo Dang mo web server tai port %PORT%...
echo.

REM Mo server trong cua so CMD rieng
start "BUSIDOL Wiki Server" cmd /k "%PYTHON_CMD% -m http.server %PORT%"

REM Doi mot chut de server kip khoi dong
timeout /t 2 /nobreak >nul

echo Dang mo trinh duyet...
start "" "%WIKI_URL%"

echo.
echo Da mo:
echo %WIKI_URL%
echo.
echo Luu y:
echo - Giu cua so "BUSIDOL Wiki Server" dang mo de website hoat dong.
echo - Muon tat web, dong cua so server do.
echo.
timeout /t 3 /nobreak >nul

endlocal
exit /b 0
