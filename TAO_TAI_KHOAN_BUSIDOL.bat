@echo off
chcp 65001 >nul
title BUSIDOL - Tao tai khoan moi

cd /d "%~dp0"

echo ==========================================
echo        BUSIDOL - TAO TAI KHOAN MOI
echo ==========================================
echo.

if not exist "serve.py" (
    echo [LOI] Khong tim thay serve.py trong thu muc nay.
    echo Hay dat file BAT nay vao thu muc goc cua BUSIDOL:
    echo E:\UserData\Desktop\busidol_offline
    echo.
    pause
    exit /b 1
)

if not exist "busidol.db" (
    echo [CANH BAO] Khong tim thay busidol.db.
    echo Neu day khong phai thu muc project dung, hay dong cua so nay.
    echo.
)

echo Luu y:
echo - Neu username da ton tai, mat khau cua tai khoan do co the bi cap nhat.
echo - Khong nen dung username cua tai khoan cu neu khong muon doi mat khau.
echo.

set /p BUSIDOL_USER=Nhap username moi: 
if "%BUSIDOL_USER%"=="" (
    echo [LOI] Username khong duoc de trong.
    echo.
    pause
    exit /b 1
)

set /p BUSIDOL_PASS=Nhap password: 
if "%BUSIDOL_PASS%"=="" (
    echo [LOI] Password khong duoc de trong.
    echo.
    pause
    exit /b 1
)

echo.
echo Dang tao/cap nhat tai khoan "%BUSIDOL_USER%"...
echo.

python .\serve.py --db .\busidol.db --add-user "%BUSIDOL_USER%" --add-pass "%BUSIDOL_PASS%"

if errorlevel 1 (
    echo.
    echo [THAT BAI] Khong tao duoc tai khoan.
    echo Kiem tra Python, serve.py va busidol.db.
) else (
    echo.
    echo [THANH CONG] Da tao/cap nhat tai khoan "%BUSIDOL_USER%".
)

echo.
pause
