@echo off
chcp 65001 >nul
echo ========================================
echo  비상장 종목 서치 데이터 업데이트
echo ========================================
cd /d "%~dp0"
python scripts\fetch_all.py
echo.
echo 완료! 아무 키나 누르세요...
pause >nul
