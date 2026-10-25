@echo off
chcp 65001 >nul
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0gdl_greeting_card_illustrator_check_v0_1.ps1"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo Illustrator GDL preflight BLOCKED. Review the server diagnostic above.
) else (
  echo Illustrator GDL preflight complete. No card was generated.
)
echo.
pause
exit /b %RC%
