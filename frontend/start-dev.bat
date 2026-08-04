@echo off
REM 一键启动前端（不依赖当前终端是否已配置 npm PATH）
set "PATH=C:\Users\Administrator\AppData\Local\nvm\v22.16.0;%PATH%"
cd /d "%~dp0"
echo Using node:
where node
echo.
npm run dev
