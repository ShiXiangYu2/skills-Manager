# Novel Studio 后端启动脚本
# 启动 FastAPI 后端服务

$BACKEND_DIR = "D:\GitHub Learn\novel-studio\backend"
$PYTHON_EXE = "D:\GitHub Learn\crewai-demo\.venv\Scripts\python.exe"

Write-Host "启动 Novel Studio 后端..." -ForegroundColor Cyan

# 检查 Python 环境
if (-not (Test-Path $PYTHON_EXE)) {
    Write-Host "✗ Python 环境不存在: $PYTHON_EXE" -ForegroundColor Red
    exit 1
}

# 检查后端目录
if (-not (Test-Path $BACKEND_DIR)) {
    Write-Host "✗ 后端目录不存在: $BACKEND_DIR" -ForegroundColor Red
    exit 1
}

# 启动后端
Write-Host "✓ 启动后端: http://127.0.0.1:8001" -ForegroundColor Green
Set-Location $BACKEND_DIR
& $PYTHON_EXE run.py
