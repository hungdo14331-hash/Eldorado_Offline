@echo off
setlocal EnableExtensions
title Clear Chrome cache

set "CHROME_USER_DATA=%LOCALAPPDATA%\Google\Chrome\User Data"
set "DRY_RUN="
set /a CLEANED=0

if /I "%~1"=="/dry-run" (
    set "DRY_RUN=1"
    echo [DRY-RUN] Chi liet ke, khong xoa file.
)

if not exist "%CHROME_USER_DATA%" (
    echo Khong tim thay thu muc Chrome:
    echo %CHROME_USER_DATA%
    pause
    exit /b 1
)

if not defined DRY_RUN (
    choice /C YN /N /M "Dong Chrome va xoa cache? [Y/N] "
    if errorlevel 2 exit /b 1

    taskkill /IM chrome.exe /F >nul 2>&1
    timeout /t 1 /nobreak >nul
)

for /d %%P in ("%CHROME_USER_DATA%\*") do (
    call :clean "%%~fP\Cache"
    call :clean "%%~fP\Code Cache"
    call :clean "%%~fP\GPUCache"
    call :clean "%%~fP\Network\Cache"
    call :clean "%%~fP\Service Worker\CacheStorage"
)

if defined DRY_RUN (
    echo.
    echo Dry-run hoan tat. Khong co file nao bi xoa.
) else (
    echo.
    echo Da xu ly %CLEANED% thu muc cache.
    echo Bookmark, mat khau va cookie khong bi xoa.
)
pause
exit /b 0

:clean
if not exist "%~1" exit /b 0
if defined DRY_RUN (
    echo [DRY-RUN] %~1
    set /a CLEANED+=1
    exit /b 0
)
rd /s /q "%~1" >nul 2>&1
if exist "%~1" (
    echo [FAIL] %~1
) else (
    echo [OK] %~1
)
set /a CLEANED+=1
exit /b 0
