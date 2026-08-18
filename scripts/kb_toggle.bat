@echo off
setlocal EnableExtensions
title 知识库系统开关
cd /d "%~dp0"

REM ===== 配置 =====
set "BACKEND_DIR=%~dp0..\backend"
set "PORT=8002"
set "URL=http://127.0.0.1:%PORT%"

REM ===== 检测并停止（按命令行匹配 python uvicorn 与本端口）=====
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'uvicorn app.main:app' -and $_.CommandLine -match '%PORT%' }; if ($p) { $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Write-Output 'RUNNING' } else { Write-Output 'STOPPED' }" > "%TEMP%\kb_check.txt"
set /p STATE=<"%TEMP%\kb_check.txt"
del "%TEMP%\kb_check.txt" >nul 2>&1

if "%STATE%"=="RUNNING" (
    echo [知识库系统] 检测到服务正在运行，已停止。
    echo 端口 %PORT% 已释放。
) else (
    echo [知识库系统] 正在启动...
    start "知识库系统 - 后端服务" /min cmd /k "cd /d %BACKEND_DIR% && .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%"
    timeout /t 3 /nobreak >nul
    echo 已启动：%URL%
    echo 服务日志窗口已最小化（标题：知识库系统 - 后端服务），关闭它或再次运行本开关即可停止。
    start "" "%URL%"
)
echo.
pause
