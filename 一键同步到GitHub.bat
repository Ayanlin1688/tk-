@echo off
chcp 65001 >nul
cd /d "%~dp0"
set GIT="C:\Program Files\Git\cmd\git.exe"
echo === [1/3] 提交修改 ===
%GIT% add -A
%GIT% commit -m "update: %date% %time%"
echo.
echo === [2/3] 推送到 GitHub ===
%GIT% push origin main
echo.
echo === [3/3] 完成 ===
pause
