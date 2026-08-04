# 一键启动前端开发服务器（兼容 Cursor 终端里找不到 npm 的情况）
$ErrorActionPreference = "Stop"
$nodeDir = "C:\Users\Administrator\AppData\Local\nvm\v22.16.0"
if (-not (Test-Path "$nodeDir\npm.cmd")) {
    Write-Error "未找到 npm，请确认 Node 已安装在: $nodeDir"
}
$env:Path = "$nodeDir;" + $env:Path
Set-Location $PSScriptRoot
Write-Host "node: $(node --version)  npm: $(npm --version)" -ForegroundColor Green
npm run dev
