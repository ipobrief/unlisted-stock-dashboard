@echo off
cd /d "%~dp0"

echo [%date% %time%] auto update start >> auto_update.log

python scripts\fetch_all.py >> auto_update.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] FETCH FAILED >> auto_update.log
    exit /b 1
)

git add -A
git diff --cached --quiet
if %errorlevel%==0 (
    echo [%date% %time%] no changes, skip push >> auto_update.log
    exit /b 0
)

git commit -m "auto data update %date%" >> auto_update.log 2>&1
git push >> auto_update.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] PUSH FAILED >> auto_update.log
    exit /b 1
)

echo [%date% %time%] done >> auto_update.log
