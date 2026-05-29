@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo  비상장 종목 서치 - 데이터 갱신 후 공유 URL 반영
echo  https://ipobrief.github.io/unlisted-stock-dashboard/
echo ============================================================
echo.

echo [1/3] 데이터 수집 중... (몇 분 걸릴 수 있습니다)
python scripts\fetch_all.py
if errorlevel 1 (
    echo.
    echo [오류] 데이터 수집에 실패했습니다. 중단합니다.
    pause
    exit /b 1
)
echo.

echo [2/3] 변경사항 커밋 중...
git add -A
git diff --cached --quiet
if %errorlevel%==0 (
    echo    변경된 내용이 없습니다. 푸시를 건너뜁니다.
    echo.
    echo 완료! 아무 키나 누르세요...
    pause >nul
    exit /b 0
)
for /f "tokens=1-3 delims=- " %%a in ("%date%") do set today=%%a-%%b-%%c
git commit -m "데이터 갱신 %today%"
echo.

echo [3/3] GitHub에 푸시 중...
git push
if errorlevel 1 (
    echo.
    echo [오류] 푸시에 실패했습니다. 인터넷 연결 또는 git 로그인을 확인하세요.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  완료! 1~2분 후 아래 주소에 반영됩니다.
echo  https://ipobrief.github.io/unlisted-stock-dashboard/
echo ============================================================
echo.
echo 아무 키나 누르세요...
pause >nul
