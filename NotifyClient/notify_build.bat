@echo off
chcp 65001 >nul
echo ============================================
echo   Сборка Corporate Notify
echo ============================================
echo.

cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Python не установлен!
    pause
    exit /b 1
)

echo [1/2] Установка зависимостей...
pip install pywebview pyinstaller --quiet

echo [2/2] Сборка exe...
pyinstaller --onefile --noconsole --name "CorporateNotify" notify.py
if %errorlevel% neq 0 (
    echo [ОШИБКА] Сборка не удалась
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Готово: dist\CorporateNotify.exe
echo ============================================
pause
