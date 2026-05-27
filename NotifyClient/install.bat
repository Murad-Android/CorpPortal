@echo off
chcp 65001 >nul
echo Установка Corporate Notify в автозагрузку...

:: Копируем exe в Program Files
if not exist "C:\Program Files\CorporateNotify" mkdir "C:\Program Files\CorporateNotify"
copy /Y "%~dp0dist\CorporateNotify.exe" "C:\Program Files\CorporateNotify\CorporateNotify.exe"

:: Добавляем в автозагрузку для всех пользователей
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "CorporateNotify" /t REG_SZ /d "\"C:\Program Files\CorporateNotify\CorporateNotify.exe\"" /f

echo.
echo Готово! Приложение будет запускаться при входе в систему.
pause
