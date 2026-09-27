$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root 'runtime\python\python.exe'
$pgBin = Join-Path $root 'runtime\postgres\bin'
$dataDir = Join-Path $root 'data\postgres'
$stateDir = Join-Path $root 'data'
$logDir = Join-Path $root 'logs'
$backend = Join-Path $root 'web_center\backend'
$envFile = Join-Path $backend '.env'
$pidFile = Join-Path $stateDir 'web.pid'
$url = 'http://127.0.0.1:8000/'
$dbPort = '55432'

function Assert-LastExitCode([string] $step) {
    if ($LASTEXITCODE -ne 0) { throw "$step 失败，退出码：$LASTEXITCODE" }
}

function Read-DbPassword {
    $line = Get-Content -LiteralPath $envFile -Encoding UTF8 |
        Where-Object { $_ -match '^DB_PASSWORD=' } |
        Select-Object -First 1
    if (-not $line) { throw '.env 中没有 DB_PASSWORD，请检查部署目录。' }
    return $line.Substring('DB_PASSWORD='.Length)
}

function Wait-For-Web {
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/v1/health' -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { return }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    throw '网页服务未能就绪，请查看 logs\web.err.log。'
}

try {
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw '部署包缺少 Python 运行环境。' }
    if (-not (Test-Path -LiteralPath (Join-Path $pgBin 'pg_ctl.exe') -PathType Leaf)) { throw '部署包缺少 PostgreSQL 运行环境。' }
    New-Item -ItemType Directory -Force -Path $stateDir, $logDir | Out-Null
    $env:PATH = "$pgBin;$env:PATH"

    if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
        $random = New-Object byte[] 32
        $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try { $generator.GetBytes($random) } finally { $generator.Dispose() }
        $password = ([BitConverter]::ToString($random)).Replace('-', '').ToLowerInvariant()
        @(
            'APP_NAME=Yinda Survey Web Center API'
            'APP_ENV=development'
            'DB_HOST=127.0.0.1'
            "DB_PORT=$dbPort"
            'DB_NAME=yinda_web_center'
            'DB_USER=yinda_app'
            "DB_PASSWORD=$password"
            'SESSION_COOKIE_SECURE=false'
        ) | Set-Content -LiteralPath $envFile -Encoding UTF8
    }
    $env:PGPASSWORD = Read-DbPassword

    if (-not (Test-Path -LiteralPath (Join-Path $dataDir 'PG_VERSION') -PathType Leaf)) {
        if (Test-Path -LiteralPath $dataDir) { throw '数据库目录已存在但没有 PG_VERSION，请先检查 data\postgres。' }
        $passwordFile = Join-Path $stateDir 'initdb-password.tmp'
        try {
            [System.IO.File]::WriteAllText($passwordFile, $env:PGPASSWORD, [Text.Encoding]::ASCII)
            Write-Host '首次使用：正在初始化本机数据库...'
            & (Join-Path $pgBin 'initdb.exe') "--pgdata=$dataDir" '--username=yinda_app' '--auth=scram-sha-256' "--pwfile=$passwordFile" '--encoding=UTF8' '--locale=C'
            Assert-LastExitCode '初始化数据库'
        } finally {
            Remove-Item -LiteralPath $passwordFile -Force -ErrorAction SilentlyContinue
        }
    }

    & (Join-Path $pgBin 'pg_ctl.exe') -D $dataDir status *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host '正在启动本机数据库...'
        & (Join-Path $pgBin 'pg_ctl.exe') -D $dataDir -l (Join-Path $logDir 'postgres.log') -o "-h 127.0.0.1 -p $dbPort" -w start
        Assert-LastExitCode '启动数据库'
    }

    $databaseExists = & (Join-Path $pgBin 'psql.exe') -X -t -A -h 127.0.0.1 -p $dbPort -U yinda_app -d postgres -c "SELECT 1 FROM pg_database WHERE datname = 'yinda_web_center'"
    Assert-LastExitCode '检查业务数据库'
    if (($databaseExists | Out-String).Trim() -ne '1') {
        & (Join-Path $pgBin 'createdb.exe') -h 127.0.0.1 -p $dbPort -U yinda_app yinda_web_center
        Assert-LastExitCode '创建业务数据库'
    }

    Push-Location $backend
    try {
        Write-Host '正在更新数据库结构...'
        & $python -m alembic upgrade head
        Assert-LastExitCode '更新数据库结构'
        if (-not (Test-Path -LiteralPath (Join-Path $stateDir 'admin-created.txt'))) {
            Write-Host '请按提示创建首位管理员账号。密码输入时不会显示。'
            & $python -m app.cli.create_admin
            Assert-LastExitCode '创建管理员'
            'Administrator setup completed.' | Set-Content -LiteralPath (Join-Path $stateDir 'admin-created.txt') -Encoding ASCII
        }
    } finally {
        Pop-Location
    }

    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $pidFile -PathType Leaf) {
        $oldPid = Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($oldPid -match '^\d+$') {
            $oldProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $oldPid" -ErrorAction SilentlyContinue
            if ($oldProcess -and $oldProcess.ExecutablePath -eq $python) {
                Wait-For-Web
                Write-Host "系统已在运行：$url"
                Start-Process $url
                exit 0
            }
        }
    }

    Write-Host '正在启动网页服务...'
    $web = Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--no-proxy-headers') -WorkingDirectory $backend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'web.out.log') -RedirectStandardError (Join-Path $logDir 'web.err.log') -PassThru
    $web.Id | Set-Content -LiteralPath $pidFile -Encoding ASCII
    Wait-For-Web
    Write-Host "启动完成：$url"
    Start-Process $url
} catch {
    Write-Host "启动失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}
