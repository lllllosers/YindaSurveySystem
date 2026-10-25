from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import shutil
import zipfile


ROOT = Path(__file__).resolve().parent
BASE_VERSION = "1.2.1"
TARGET_VERSION = "1.2.2"
RELEASE_ROOT = ROOT / "release"
DEFAULT_SOURCE_RELEASE = RELEASE_ROOT / "YindaSurveySystem_V1.2.2_Windows_x64"
UPDATE_NAME = "YindaSurveySystem_V1.2.1_to_V1.2.2_Update"
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
    Write-Host ("[V1.2.2] " + $Message) -ForegroundColor Cyan
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
        if ($candidateVersion -eq "1.2.1") {
            return $parentCandidate
        }
    }

    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "请选择当前 V1.2.1 程序所在文件夹"
    $dialog.ShowNewFolderButton = $false

    $result = $dialog.ShowDialog()
    if ($result -ne [System.Windows.Forms.DialogResult]::OK) {
        throw "未选择 V1.2.1 程序目录，升级已取消。"
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
    Write-Host "V1.2.1 -> V1.2.2 安全升级程序"
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
    if ($currentVersion -ne "1.2.1") {
        $shownVersion = if ($null -eq $currentVersion) { "未知" } else { "V" + $currentVersion }
        throw ("本升级包仅支持 V1.2.1 -> V1.2.2。当前目录识别版本：" + $shownVersion)
    }

    Write-Step ("目标目录：" + $TargetDir)

    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $upgradeBackupRoot = Join-Path $TargetDir ("upgrade_backups\V1.2.1_to_V1.2.2_" + $timestamp)
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
        Copy-Item -LiteralPath $oldReleaseInfo -Destination (Join-Path $upgradeBackupRoot "RELEASE_INFO_V1.2.1.txt") -Force
    }

    New-Item -ItemType Directory -Path $rollbackDir -Force | Out-Null
    $movedNames = New-Object System.Collections.ArrayList
    $replacementStarted = $false

    try {
        Write-Step "准备替换 V1.2.1 程序文件"

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
        Write-Step "安装 V1.2.2 程序文件"

        foreach ($payloadItem in Get-ChildItem -LiteralPath $PayloadDir -Force) {
            Copy-Item -LiteralPath $payloadItem.FullName -Destination $TargetDir -Recurse -Force
        }

        $newVersion = Get-ReleaseVersion $TargetDir
        if ($newVersion -ne "1.2.2") {
            throw "程序文件复制完成，但目标目录未识别为 V1.2.2。"
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
        "YindaSurveySystem V1.2.1 -> V1.2.2"
        ("Completed=" + (Get-Date).ToString("s"))
        ("Target=" + $TargetDir)
        ("LocalDataBackup=" + $dataBackupDir)
        ""
        "程序文件升级已经完成。"
        "V1.2.2 为 UI 补丁，不新增数据库迁移或首次启动迁移标记；历史迁移保护保持不变。"
    ) | Set-Content -LiteralPath $completedLog -Encoding UTF8

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "V1.2.2 程序文件升级完成。" -ForegroundColor Green
    if (Test-Path -LiteralPath $dataBackupDir) {
        Write-Host ("local_data 文件级备份：" + $dataBackupDir)
    }
    Write-Host "现在可以启动 YindaSurveySystem.exe。"
    Write-Host "V1.2.2 不新增数据库迁移；安装前的完整 local_data 文件备份已保留。"
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
echo Starting YindaSurveySystem V1.2.1 to V1.2.2 updater...
echo.

powershell.exe ^
  -NoProfile ^
  -ExecutionPolicy Bypass ^
  -File "%~dp0update_v1_2_2.ps1"

set "EXIT_CODE=%ERRORLEVEL%"

echo.

if not "%EXIT_CODE%"=="0" (
    echo [FAILED] V1.2.2 update was not completed.
) else (
    echo [SUCCESS] V1.2.2 program update completed.
)

echo.
pause
exit /b %EXIT_CODE%
'''


UPGRADE_NOTE = r'''引大入秦工程现状调查采集系统
V1.2.1 -> V1.2.2 升级说明
============================================================

【适用范围】
仅支持正式版 V1.2.1 升级到 V1.2.2；其他来源版本会停止。
新安装请使用 YindaSurveySystem_V1.2.2_Windows_x64.zip。
本包携带完整程序 payload，统一替换程序文件，不是少量内部文件的差分补丁。

【升级方法】
1. 退出软件，建议另行留存现有 local_data 备份。
2. 将升级 ZIP 解压到独立文件夹，双击“升级到V1.2.2.bat”。
3. 选择现有 V1.2.1 安装目录，等待校验、备份和替换完成。
4. 从原安装目录启动 YindaSurveySystem.exe，确认版本为 V1.2.2。
5. 检查原有项目、调查记录、影像和列表滚动，无需重新导入数据。

【数据保护与兼容】
程序文件替换前，升级器完整复制 local_data 到：
    <原程序目录>\upgrade_backups\V1.2.1_to_V1.2.2_<时间>\local_data
校验失败或来源版本不符时停止；程序文件替换失败时回滚旧程序。
升级器不删除、不覆盖原 local_data。
V1.2.2 仅修复列表 UI，不改变 SQLite schema、业务字段、UID 或 revision，
不新增数据库迁移、迁移标记或 pre_v1_2_2_upgrade 首次启动备份。
历史 pre_v1_2_0_upgrade、pre_v1_2_1_upgrade 保护逻辑保持原样；
已完成的历史迁移不属于本次新增能力。任务协议 V3、成果协议 2.2 不变。

【回退】
程序替换失败时升级器自动恢复已移动的旧程序文件。
升级成功后的人工回退：关闭软件，使用原 V1.2.1 完整正式包恢复程序文件，
先另存当前 local_data，再按需恢复上述备份；不要盲目覆盖升级后新增的数据。

【注意】
升级过程中不要启动旧程序，不要手工复制 update_payload 到 local_data。
保留完整安装目录和 local_data；不得只替换 EXE 或只复制部分运行库。
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
            "V1.2.2 完整发布目录不完整：\n"
            + "\n".join(f"- {item}" for item in missing)
        )

    release_info = (source_release / "RELEASE_INFO.txt").read_text(
        encoding="utf-8",
        errors="replace",
    )
    if "Version=V1.2.2" not in release_info.splitlines():
        raise RuntimeError("source release 不是 V1.2.2。")

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
        update_dir / "升级到V1.2.2.bat",
        update_dir / "update_v1_2_2.ps1",
        update_dir / "V1.2.2_升级说明.txt",
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
        "升级到V1.2.2.bat",
        "update_v1_2_2.ps1",
        "V1.2.2_升级说明.txt",
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

    (update_dir / "update_v1_2_2.ps1").write_text(
        POWERSHELL_UPDATER,
        encoding="utf-8-sig",
        newline="\r\n",
    )
    (update_dir / "升级到V1.2.2.bat").write_text(
        BAT_UPDATER,
        encoding="utf-8",
        newline="\r\n",
    )
    (update_dir / "V1.2.2_升级说明.txt").write_text(
        UPGRADE_NOTE,
        encoding="utf-8-sig",
        newline="\r\n",
    )
    (update_dir / "UPDATE_INFO.txt").write_text(
        (
            "YindaSurveySystem Update Package\n"
            "PackageType=SafeFullPayloadUpdater\n"
            "FromVersion=V1.2.1\n"
            "ToVersion=V1.2.2\n"
            "Preserve=local_data\n"
            "PayloadHashManifest=UPDATE_MANIFEST.sha256\n"
            "\n"
            "该包用于已有 V1.2.1 安装的安全覆盖升级，不是源码级差分补丁。\n"
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
    print("[SUCCESS] V1.2.1 -> V1.2.2 update package completed.")
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
        help="Validated V1.2.2 full release directory.",
    )
    args = parser.parse_args()
    build_update_package(Path(args.source_release))


if __name__ == "__main__":
    main()
