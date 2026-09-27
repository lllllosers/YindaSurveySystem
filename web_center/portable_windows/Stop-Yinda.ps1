$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $root 'data\web.pid'
$python = Join-Path $root 'runtime\python\python.exe'
$pgCtl = Join-Path $root 'runtime\postgres\bin\pg_ctl.exe'
$dataDir = Join-Path $root 'data\postgres'

try {
    if (Test-Path -LiteralPath $pidFile -PathType Leaf) {
        $webPid = Get-Content -LiteralPath $pidFile | Select-Object -First 1
        if ($webPid -match '^\d+$') {
            $webProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $webPid" -ErrorAction SilentlyContinue
            if ($webProcess -and $webProcess.ExecutablePath -eq $python) {
                Stop-Process -Id ([int] $webPid) -ErrorAction Stop
            }
        }
        Remove-Item -LiteralPath $pidFile -Force
    }
    if (Test-Path -LiteralPath (Join-Path $dataDir 'PG_VERSION') -PathType Leaf) {
        & $pgCtl -D $dataDir status *> $null
        if ($LASTEXITCODE -eq 0) {
            & $pgCtl -D $dataDir -m fast -w stop
            if ($LASTEXITCODE -ne 0) { throw '停止数据库失败。' }
        }
    }
    Write-Host '引大 Web 系统已停止。'
} catch {
    Write-Host "停止失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
