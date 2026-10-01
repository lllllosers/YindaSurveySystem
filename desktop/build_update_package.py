from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import shutil
import zipfile


ROOT = Path(__file__).resolve().parent
BASE_VERSION = "1.1.1"
TARGET_VERSION = "1.2.0"
RELEASE_ROOT = ROOT / "release"
DEFAULT_SOURCE_RELEASE = RELEASE_ROOT / "YindaSurveySystem_V1.2.0_Windows_x64"
UPDATE_NAME = "YindaSurveySystem_V1.1.1_to_V1.2.0_Update"
FORBIDDEN_RUNTIME_NAMES = {"local_data"}
FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".sqlite3"}


POWERSHELL_UPDATER = r'''param(
    [string]$TargetDir = ""
)

$ErrorActionPreference = "Stop"
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PayloadDir = Join-Path $PackageRoot "update_payload"
$ManifestPath = Join-Path $PackageRoot "UPDATE_MANIFEST.sha256"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host ("[V1.2.0] " + $Message) -ForegroundColor Cyan
}

function Get-ReleaseVersion {
    param([string]$Directory)

    $infoPath = Join-Path $Directory "RELEASE_INFO.txt"
    if (-not (Test-Path -LiteralPath $infoPath -PathType Leaf)) {
        return $null
    }

    $match = Select-String -LiteralPath $infoPath -Pattern '^Version=V(.+)$' | Select-Object -First 1
    if ($null -eq $match) {
        return $null
    }

    return $match.Matches[0].Groups[1].Value.Trim()
}

function Test-InstallDirectory {
    param([string]$Directory)

    if ([string]::IsNullOrWhiteSpace($Directory)) {
        return $false
    }

    $exePath = Join-Path $Directory "YindaSurveySystem.exe"
    return (Test-Path -LiteralPath $exePath -PathType Leaf)
}

function Select-InstallDirectory {
    $parentCandidate = Split-Path -Parent $PackageRoot

    if (Test-InstallDirectory $parentCandidate) {
        $candidateVersion = Get-ReleaseVersion $parentCandidate
        if ($candidateVersion -eq "1.1.1") {
            return $parentCandidate
        }
    }

    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "请选择当前 V1.1.1 程序所在文件夹"
    $dialog.ShowNewFolderButton = $false

    $result = $dialog.ShowDialog()
    if ($result -ne [System.Windows.Forms.DialogResult]::OK) {
        throw "未选择 V1.1.1 程序目录，升级已取消。"
    }

    return $dialog.SelectedPath
}

function Verify-Payload {
    Write-Step "校验升级包完整性"

    if (-not (Test-Path -LiteralPath $PayloadDir -PathType Container)) {
        throw "升级包缺少 update_payload。"
    }

    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        throw "升级包缺少 UPDATE_MANIFEST.sha256。"
    }

    $lines = Get-Content -LiteralPath $ManifestPath -Encoding UTF8

    foreach ($line in $lines) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $parts = $line -split "`t", 2
        if ($parts.Count -ne 2) {
            throw "升级包校验清单格式无效。"
        }

        $expected = $parts[0].Trim().ToLowerInvariant()
        $relative = $parts[1].Trim() -replace '/', '\\'
        $filePath = Join-Path $PackageRoot $relative

        if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) {
            throw ("升级包文件缺失：" + $relative)
        }

        $actual = (Get-FileHash -LiteralPath $filePath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $expected) {
            throw ("升级包文件校验失败：" + $relative)
        }
    }
}

function Restore-ProgramFiles {
    param(
        [string]$InstallDir,
        [string]$RollbackDir,
        [System.Collections.ArrayList]$MovedNames,
        [bool]$ReplacementStarted
    )

    Write-Host ""
    Write-Host "正在回滚程序文件..." -ForegroundColor Yellow

    if ($ReplacementStarted) {
        Get-ChildItem -LiteralPath $PayloadDir -Force | ForEach-Object {
            $destination = Join-Path $InstallDir $_.Name
            if (Test-Path -LiteralPath $destination) {
                Remove-Item -LiteralPath $destination -Recurse -Force
            }
        }
    }

    for ($index = $MovedNames.Count - 1; $index -ge 0; $index--) {
        $name = [string]$MovedNames[$index]
        $source = Join-Path $RollbackDir $name
        $destination = Join-Path $InstallDir $name

        if (Test-Path -LiteralPath $source) {
            Move-Item -LiteralPath $source -Destination $destination -Force
        }
    }
}

try {
    Write-Host "============================================================"
    Write-Host "引大入秦工程现状调查采集系统"
    Write-Host "V1.1.1 -> V1.2.0 安全升级程序"
    Write-Host "============================================================"

    Verify-Payload

    $running = Get-Process -Name "YindaSurveySystem" -ErrorAction SilentlyContinue
    if ($null -ne $running) {
        throw "检测到引大调查系统仍在运行。请完全关闭程序后重新升级。"
    }

    if ([string]::IsNullOrWhiteSpace($TargetDir)) {
        $TargetDir = Select-InstallDirectory
    }

    $TargetDir = [System.IO.Path]::GetFullPath($TargetDir)
    if (-not (Test-InstallDirectory $TargetDir)) {
        throw "所选目录不是有效的引大调查系统安装目录。"
    }

    $currentVersion = Get-ReleaseVersion $TargetDir
    if ($currentVersion -ne "1.1.1") {
        $shownVersion = if ($null -eq $currentVersion) { "未知" } else { "V" + $currentVersion }
        throw ("本升级包仅支持 V1.1.1 -> V1.2.0。当前目录识别版本：" + $shownVersion)
    }

    Write-Step ("目标目录：" + $TargetDir)

    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $upgradeBackupRoot = Join-Path $TargetDir ("upgrade_backups\V1.1.1_to_V1.2.0_" + $timestamp)
    $dataBackupDir = Join-Path $upgradeBackupRoot "local_data"
    $rollbackDir = Join-Path $upgradeBackupRoot "program_rollback"

    New-Item -ItemType Directory -Path $upgradeBackupRoot -Force | Out-Null

    $localDataDir = Join-Path $TargetDir "local_data"
    if (Test-Path -LiteralPath $localDataDir -PathType Container) {
        Write-Step "备份现有 local_data"
        Copy-Item -LiteralPath $localDataDir -Destination $dataBackupDir -Recurse -Force
        if (-not (Test-Path -LiteralPath $dataBackupDir -PathType Container)) {
            throw "local_data 备份失败，升级已停止。"
        }
    }
    else {
        Write-Host ""
        Write-Host "当前安装目录没有 local_data；继续执行程序更新。" -ForegroundColor Yellow
    }

    $oldReleaseInfo = Join-Path $TargetDir "RELEASE_INFO.txt"
    if (Test-Path -LiteralPath $oldReleaseInfo -PathType Leaf) {
        Copy-Item -LiteralPath $oldReleaseInfo -Destination (Join-Path $upgradeBackupRoot "RELEASE_INFO_V1.1.1.txt") -Force
    }

    New-Item -ItemType Directory -Path $rollbackDir -Force | Out-Null
    $movedNames = New-Object System.Collections.ArrayList
    $replacementStarted = $false

    try {
        Write-Step "准备替换 V1.1.1 程序文件"

        foreach ($payloadItem in Get-ChildItem -LiteralPath $PayloadDir -Force) {
            if ($payloadItem.Name -eq "local_data") {
                throw "升级 payload 非法：不得包含 local_data。"
            }

            $destination = Join-Path $TargetDir $payloadItem.Name
            if (Test-Path -LiteralPath $destination) {
                Move-Item -LiteralPath $destination -Destination $rollbackDir -Force
                [void]$movedNames.Add($payloadItem.Name)
            }
        }

        $replacementStarted = $true
        Write-Step "安装 V1.2.0 程序文件"

        foreach ($payloadItem in Get-ChildItem -LiteralPath $PayloadDir -Force) {
            Copy-Item -LiteralPath $payloadItem.FullName -Destination $TargetDir -Recurse -Force
        }

        $newVersion = Get-ReleaseVersion $TargetDir
        if ($newVersion -ne "1.2.0") {
            throw "程序文件复制完成，但目标目录未识别为 V1.2.0。"
        }

        $newExe = Join-Path $TargetDir "YindaSurveySystem.exe"
        if (-not (Test-Path -LiteralPath $newExe -PathType Leaf)) {
            throw "升级后未找到 YindaSurveySystem.exe。"
        }
    }
    catch {
        Restore-ProgramFiles -InstallDir $TargetDir -RollbackDir $rollbackDir -MovedNames $movedNames -ReplacementStarted $replacementStarted
        throw
    }

    if (Test-Path -LiteralPath $rollbackDir) {
        Remove-Item -LiteralPath $rollbackDir -Recurse -Force
    }

    $completedLog = Join-Path $upgradeBackupRoot "UPDATE_COMPLETED.txt"
    @(
        "YindaSurveySystem V1.1.1 -> V1.2.0"
        ("Completed=" + (Get-Date).ToString("s"))
        ("Target=" + $TargetDir)
        ("LocalDataBackup=" + $dataBackupDir)
        ""
        "程序文件升级已经完成。"
        "首次启动 V1.2.0 时，应用自身还会在数据库迁移前创建 pre_v1_2_0_upgrade SQLite 备份。"
    ) | Set-Content -LiteralPath $completedLog -Encoding UTF8

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "V1.2.0 程序文件升级完成。" -ForegroundColor Green
    if (Test-Path -LiteralPath $dataBackupDir) {
        Write-Host ("local_data 文件级备份：" + $dataBackupDir)
    }
    Write-Host "现在可以启动 YindaSurveySystem.exe。"
    Write-Host "首次启动会继续执行 V1.2.0 数据库级安全备份与兼容迁移。"
    Write-Host "============================================================" -ForegroundColor Green
    exit 0
}
catch {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "升级未完成。" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "现有 local_data 不会被升级程序删除或覆盖。" -ForegroundColor Yellow
    Write-Host "============================================================" -ForegroundColor Red
    exit 1
}
'''


BAT_UPDATER = r'''@echo off
setlocal EnableExtensions

cd /d "%~dp0"

echo.
echo Starting YindaSurveySystem V1.1.1 to V1.2.0 updater...
echo.

powershell.exe ^
  -NoProfile ^
  -ExecutionPolicy Bypass ^
  -File "%~dp0update_v1_2_0.ps1"

set "EXIT_CODE=%ERRORLEVEL%"

echo.

if not "%EXIT_CODE%"=="0" (
    echo [FAILED] V1.2.0 update was not completed.
) else (
    echo [SUCCESS] V1.2.0 program update completed.
)

echo.
pause
exit /b %EXIT_CODE%
'''


UPGRADE_NOTE = r'''引大入秦工程现状调查采集系统
V1.1.1 -> V1.2.0 升级说明
============================================================

【这个包是什么】
这是 V1.1.1 -> V1.2.0 专用安全升级包。

它不是只替换几个内部文件的“差分补丁”。升级包内携带经过完整校验的 V1.2.0 程序 payload，由升级程序统一替换 V1.1.1 程序文件，同时明确保留 local_data。这样可以避免 PyInstaller 内部文件漏覆盖或旧文件混用。

【适用范围】
仅用于当前正式版 V1.1.1 升级到 V1.2.0。

全新电脑、重装或没有既有 V1.1.1 安装目录时，请使用完整发布包：
YindaSurveySystem_V1.2.0_Windows_x64.zip

【升级方法】
1. 完全关闭“引大入秦工程现状调查采集系统”。
2. 将本升级 ZIP 解压到任意独立文件夹。
3. 双击“升级到V1.2.0.bat”。
4. 选择当前 V1.1.1 程序所在文件夹。
5. 等待提示“V1.2.0 程序文件升级完成”。
6. 启动原程序目录中的 YindaSurveySystem.exe。
7. 首次启动时，V1.2.0 会自动完成数据库级安全备份和兼容迁移。

【双重数据保护】
第一层：升级程序在替换程序文件前复制完整 local_data 到：
    <原程序目录>\upgrade_backups\V1.1.1_to_V1.2.0_<时间>\local_data

第二层：V1.2.0 首次启动、数据库迁移之前，再生成：
    local_data\backups\yinda_survey_<时间>_pre_v1_2_0_upgrade.db

升级程序不会删除或覆盖原 local_data。

【升级后的历史桩号】
11张原单桩号附表：
    旧单桩号 -> 起始桩号
    终止桩号 -> 留空待补充

历史“录入完成”状态保持不变。业务编号、revision、source_revision 和历史表单版本保持。

【注意】
- 升级过程中不要启动旧程序。
- 不要把 update_payload 目录手工复制到 local_data。
- 不要删除 local_data。
- 若升级程序识别到的版本不是 V1.1.1，会主动停止。
'''


def calculate_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def find_forbidden_payload_artifacts(payload_dir: Path):
    problems = []
    for path in payload_dir.rglob("*"):
        relative = path.relative_to(payload_dir)
        if any(part.lower() in FORBIDDEN_RUNTIME_NAMES for part in relative.parts):
            problems.append(relative.as_posix())
            continue
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            problems.append(relative.as_posix())
    return sorted(set(problems))


def validate_source_release(source_release: Path) -> None:
    source_release = source_release.resolve()
    required = (
        source_release / "YindaSurveySystem.exe",
        source_release / "_internal",
        source_release / "templates",
        source_release / "RELEASE_INFO.txt",
    )
    missing = [path for path in required if not path.exists()]
    if missing:
        raise RuntimeError(
            "V1.2.0 完整发布目录不完整：\n"
            + "\n".join(f"- {item}" for item in missing)
        )

    release_info = (source_release / "RELEASE_INFO.txt").read_text(
        encoding="utf-8",
        errors="replace",
    )
    if "Version=V1.2.0" not in release_info:
        raise RuntimeError("source release 不是 V1.2.0。")

    forbidden = find_forbidden_payload_artifacts(source_release)
    if forbidden:
        raise RuntimeError(
            "完整发布目录含有禁止进入升级 payload 的运行数据：\n"
            + "\n".join(f"- {item}" for item in forbidden)
        )


def write_manifest(payload_dir: Path, manifest_path: Path) -> None:
    lines = []
    for path in sorted(item for item in payload_dir.rglob("*") if item.is_file()):
        relative = (Path("update_payload") / path.relative_to(payload_dir)).as_posix()
        lines.append(f"{calculate_sha256(path)}\t{relative}")
    manifest_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def verify_update_tree(update_dir: Path) -> None:
    required = (
        update_dir / "升级到V1.2.0.bat",
        update_dir / "update_v1_2_0.ps1",
        update_dir / "V1.2.0_升级说明.txt",
        update_dir / "UPDATE_INFO.txt",
        update_dir / "UPDATE_MANIFEST.sha256",
        update_dir / "update_payload" / "YindaSurveySystem.exe",
        update_dir / "update_payload" / "_internal",
        update_dir / "update_payload" / "templates",
        update_dir / "update_payload" / "RELEASE_INFO.txt",
    )
    missing = [path for path in required if not path.exists()]
    if missing:
        raise RuntimeError(
            "升级包目录校验失败：\n"
            + "\n".join(f"- missing: {item}" for item in missing)
        )

    forbidden = find_forbidden_payload_artifacts(update_dir / "update_payload")
    if forbidden:
        raise RuntimeError(
            "升级 payload 中存在运行数据：\n"
            + "\n".join(f"- {item}" for item in forbidden)
        )


def verify_zip(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as archive:
        names = set(archive.namelist())

    required = {
        "升级到V1.2.0.bat",
        "update_v1_2_0.ps1",
        "V1.2.0_升级说明.txt",
        "UPDATE_INFO.txt",
        "UPDATE_MANIFEST.sha256",
        "update_payload/YindaSurveySystem.exe",
        "update_payload/RELEASE_INFO.txt",
    }
    missing = sorted(required - names)
    if missing:
        raise RuntimeError(
            "升级 ZIP 校验失败：\n"
            + "\n".join(f"- missing: {item}" for item in missing)
        )

    forbidden = [
        name
        for name in names
        if (
            "/local_data/" in ("/" + name.lower())
            or name.lower().startswith("local_data/")
            or Path(name).suffix.lower() in FORBIDDEN_SUFFIXES
        )
    ]
    if forbidden:
        raise RuntimeError(
            "升级 ZIP 含有禁止的运行数据：\n"
            + "\n".join(f"- {item}" for item in forbidden[:30])
        )


def build_update_package(
    source_release: Path,
    *,
    release_root: Path = RELEASE_ROOT,
):
    source_release = Path(source_release).resolve()
    release_root = Path(release_root).resolve()
    validate_source_release(source_release)

    update_dir = release_root / UPDATE_NAME
    zip_path = release_root / f"{UPDATE_NAME}.zip"
    checksum_path = release_root / f"{UPDATE_NAME}.zip.sha256.txt"

    remove_path(update_dir)
    remove_path(zip_path)
    remove_path(checksum_path)

    release_root.mkdir(parents=True, exist_ok=True)
    update_dir.mkdir(parents=True, exist_ok=True)

    payload_dir = update_dir / "update_payload"
    shutil.copytree(source_release, payload_dir)

    (update_dir / "update_v1_2_0.ps1").write_text(
        POWERSHELL_UPDATER,
        encoding="utf-8-sig",
        newline="\r\n",
    )
    (update_dir / "升级到V1.2.0.bat").write_text(
        BAT_UPDATER,
        encoding="utf-8",
        newline="\r\n",
    )
    (update_dir / "V1.2.0_升级说明.txt").write_text(
        UPGRADE_NOTE,
        encoding="utf-8-sig",
        newline="\r\n",
    )
    (update_dir / "UPDATE_INFO.txt").write_text(
        (
            "YindaSurveySystem Update Package\n"
            "PackageType=SafeFullPayloadUpdater\n"
            "FromVersion=V1.1.1\n"
            "ToVersion=V1.2.0\n"
            "Preserve=local_data\n"
            "PayloadHashManifest=UPDATE_MANIFEST.sha256\n"
            "\n"
            "该包用于已有 V1.1.1 安装的安全覆盖升级，不是源码级差分补丁。\n"
        ),
        encoding="utf-8",
        newline="\n",
    )

    write_manifest(payload_dir, update_dir / "UPDATE_MANIFEST.sha256")
    verify_update_tree(update_dir)

    created_zip = Path(
        shutil.make_archive(
            str(release_root / UPDATE_NAME),
            "zip",
            root_dir=update_dir,
        )
    )
    verify_zip(created_zip)

    checksum = calculate_sha256(created_zip)
    checksum_path.write_text(
        f"{checksum}  {created_zip.name}\n",
        encoding="ascii",
        newline="\n",
    )

    print()
    print("=" * 72)
    print("[SUCCESS] V1.1.1 -> V1.2.0 update package completed.")
    print(f"Directory: {update_dir}")
    print(f"ZIP:       {created_zip}")
    print(f"SHA256:    {checksum_path}")
    print("=" * 72)

    return {
        "update_dir": update_dir,
        "zip_path": created_zip,
        "checksum_path": checksum_path,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-release",
        default=str(DEFAULT_SOURCE_RELEASE),
        help="Validated V1.2.0 full release directory.",
    )
    args = parser.parse_args()
    build_update_package(Path(args.source_release))


if __name__ == "__main__":
    main()
