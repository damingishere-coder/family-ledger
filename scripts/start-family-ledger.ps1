param(
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontendRoot = Join-Path $projectRoot 'frontend'
$frontendIndex = Join-Path $frontendRoot 'dist\index.html'
$serviceUrl = 'http://127.0.0.1:8767'

Set-Location -LiteralPath $projectRoot

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host '首次运行：正在创建 Python 本地环境…'
    py -3.12 -m venv (Join-Path $projectRoot '.venv')
}

& $venvPython -m pip install --disable-pip-version-check -r (Join-Path $projectRoot 'requirements.txt')

if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot 'node_modules'))) {
    Write-Host '首次运行：正在安装前端本地依赖…'
    Push-Location -LiteralPath $frontendRoot
    try {
        if (Test-Path -LiteralPath (Join-Path $frontendRoot 'package-lock.json')) {
            npm ci
        } else {
            npm install
        }
    } finally {
        Pop-Location
    }
}

if (-not (Test-Path -LiteralPath $frontendIndex)) {
    Write-Host '正在生成本地网页资源…'
    Push-Location -LiteralPath $frontendRoot
    try {
        npm run build
    } finally {
        Pop-Location
    }
}

if (-not $NoBrowser) {
    Start-Process $serviceUrl
}

Write-Host "家庭快捷月度统计台正在启动：$serviceUrl"
& $venvPython (Join-Path $projectRoot 'scripts\serve.py') --host 127.0.0.1 --port 8767
