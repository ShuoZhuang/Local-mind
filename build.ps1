$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$gpuPythonPath = Join-Path $projectRoot ".venv_gpu\Scripts\python.exe"
$cpuPythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pythonPath = if (Test-Path -LiteralPath $gpuPythonPath) { $gpuPythonPath } else { $cpuPythonPath }

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "未找到项目虚拟环境，请先运行 run.ps1 中的创建和安装命令。"
}

Push-Location $projectRoot
try {
    & $pythonPath -m PyInstaller --noconfirm --clean --windowed --name LocalMind app\main.py
} finally {
    Pop-Location
}
