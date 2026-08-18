@echo off
setlocal EnableExtensions
title 知识库系统启动
cd /d "%~dp0"

REM ===== 配置 =====
REM 相对路径优先（bat 在项目 scripts 目录时生效）；否则回退到本机绝对路径
set "BACKEND_DIR=%~dp0..\backend"
if not exist "%BACKEND_DIR%\.venv\Scripts\python.exe" set "BACKEND_DIR=D:\dsAgentproject\knowledge-base\backend"
set "PORT=8002"
set "URL=http://127.0.0.1:%PORT%"

if not exist "%BACKEND_DIR%\.venv\Scripts\python.exe" (
    echo [错误] 找不到后端目录：%BACKEND_DIR%
    echo 请编辑本文件顶部的 BACKEND_DIR，改为实际路径后重试。
    pause
    exit /b 1
)

REM ===== 检查是否已在运行（端口探测）=====
powershell -NoProfile -Command "if (Test-NetConnection 127.0.0.1 -Port %PORT% -WarningAction SilentlyContinue -InformationLevel Quiet) { 'UP' } else { 'DOWN' }" > "%TEMP%\kb_up.txt"
set /p ST=<"%TEMP%\kb_up.txt"
del "%TEMP%\kb_up.txt" >nul 2>&1

if "%ST%"=="UP" (
    echo [知识库系统] 服务已在运行：%URL%
) else (
    echo [知识库系统] 正在启动...
    start "知识库系统 - 后端服务" /min cmd /k "cd /d %BACKEND_DIR% && .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%"
    timeout /t 5 /nobreak >nul
    echo 已启动：%URL%
)
start "" "%URL%"
echo.
pause
