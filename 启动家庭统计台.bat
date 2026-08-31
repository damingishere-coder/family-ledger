@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-family-ledger.ps1"
if errorlevel 1 (
  echo.
  echo 启动失败，请保留本窗口并把上方错误信息发给 Codex。
  pause
)
endlocal
