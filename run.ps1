$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$gpuPythonPath = Join-Path $projectRoot ".venv_gpu\Scripts\python.exe"
$cpuPythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pythonPath = if (Test-Path -LiteralPath $gpuPythonPath) { $gpuPythonPath } else { $cpuPythonPath }

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Host "未找到 004 的虚拟环境。请先运行："
    Write-Host "python -m venv --system-site-packages .venv_gpu"
    Write-Host ".\.venv_gpu\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

Push-Location $projectRoot
try {
    & $pythonPath -c "import torch; print('LocalMind GPU:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
    & $pythonPath -m app.main
} finally {
    Pop-Location
}
