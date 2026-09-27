$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root 'runtime\python\python.exe'
$pgBin = Join-Path $root 'runtime\postgres\bin'
$backend = Join-Path $root 'web_center\backend'
if (-not (Test-Path -LiteralPath (Join-Path $backend '.env') -PathType Leaf)) {
    Write-Host '请先双击 Start-Yinda.bat 完成初始化。' -ForegroundColor Red
    exit 1
}
$env:PATH = "$pgBin;$env:PATH"
Push-Location $backend
try {
    & $python -m app.cli.backup_web_center
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
