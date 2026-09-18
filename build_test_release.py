from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import importlib.util
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent

VENV_PYTHON = (
    ROOT
    / ".venv"
    / "Scripts"
    / "python.exe"
)

SPEC_PATH = (
    ROOT
    / "YindaSurveySystem.spec"
)

ICON_PATH = (
    ROOT
    / "assets"
    / "app_icon.ico"
)

TEMPLATES_DIR = (
    ROOT
    / "templates"
)

BUILD_DIR = (
    ROOT
    / "build"
)

DIST_DIR = (
    ROOT
    / "dist"
)

DIST_APP = (
    DIST_DIR
    / "YindaSurveySystem"
)

RELEASE_ROOT = (
    ROOT
    / "release"
)


def load_version_info():
    version_path = (
        ROOT
        / "src"
        / "version.py"
    )

    if not version_path.exists():
        raise RuntimeError(
            "src/version.py does not exist."
        )

    spec = importlib.util.spec_from_file_location(
        "yinda_version",
        version_path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            "Could not load src/version.py."
        )

    module = (
        importlib.util.module_from_spec(
            spec
        )
    )

    spec.loader.exec_module(
        module
    )

    version = str(
        getattr(
            module,
            "APP_VERSION",
            "",
        )
    ).strip()

    stage = str(
        getattr(
            module,
            "APP_STAGE",
            "",
        )
    ).strip()

    app_name = str(
        getattr(
            module,
            "APP_NAME",
            "YindaSurveySystem",
        )
    ).strip()

    if not version:
        raise RuntimeError(
            "APP_VERSION is empty."
        )

    if not stage:
        raise RuntimeError(
            "APP_STAGE is empty."
        )

    return {
        "version": version,
        "stage": stage,
        "app_name": app_name,
    }


def check_required_paths():
    required = (
        VENV_PYTHON,
        SPEC_PATH,
        ICON_PATH,
        TEMPLATES_DIR,
        ROOT / "run_tests.py",
        ROOT / "src" / "version.py",
    )

    missing = [
        path
        for path in required
        if not path.exists()
    ]

    if missing:
        lines = "\n".join(
            f"- {path}"
            for path in missing
        )

        raise RuntimeError(
            "Required build files are missing:\n"
            + lines
        )


def run_command(
    command,
    *,
    label,
):
    print()
    print(
        f"[RUN] {label}"
    )
    print(
        " ".join(
            str(part)
            for part in command
        )
    )

    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed "
            f"(exit code {result.returncode})."
        )


def remove_path(
    path,
):
    if not path.exists():
        return

    if path.is_dir():
        shutil.rmtree(
            path
        )
    else:
        path.unlink()


def copy_release_docs(
    *,
    release_dir,
    version,
):
    docs_dir = (
        ROOT
        / "docs"
    )

    candidates = (
        (
            docs_dir
            / (
                f"V{version}_"
                "甲方测试说明.txt"
            ),
            release_dir
            / (
                f"甲方测试说明_V"
                f"{version}.txt"
            ),
        ),
        (
            docs_dir
            / (
                f"V{version}_"
                "甲方测试反馈模板.txt"
            ),
            release_dir
            / (
                f"甲方测试反馈模板_V"
                f"{version}.txt"
            ),
        ),
    )

    copied = []

    for (
        source,
        target,
    ) in candidates:
        if not source.exists():
            continue

        shutil.copy2(
            source,
            target,
        )

        copied.append(
            target
        )

    return copied


def write_release_info(
    *,
    release_dir,
    version_info,
):
    commit = "unknown"

    try:
        result = subprocess.run(
            [
                "git",
                "rev-parse",
                "--short",
                "HEAD",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        if result.returncode == 0:
            value = (
                result.stdout
                .strip()
            )

            if value:
                commit = value

    except OSError:
        pass

    info_path = (
        release_dir
        / "RELEASE_INFO.txt"
    )

    text = (
        f"{version_info['app_name']}\n"
        "\n"
        f"Version=V{version_info['version']}\n"
        f"Stage={version_info['stage']}\n"
        "BuildTime="
        f"{datetime.now().astimezone().isoformat(timespec='seconds')}\n"
        f"GitCommit={commit}\n"
        "\n"
        "该目录为阶段性测试发布包。\n"
        "如目录中包含甲方测试说明，请先阅读测试说明后使用。\n"
    )

    info_path.write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )

    return info_path


def calculate_sha256(
    path,
):
    digest = sha256()

    with open(
        path,
        "rb",
    ) as source:
        while True:
            chunk = source.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def build_release():
    check_required_paths()

    version_info = (
        load_version_info()
    )

    version = (
        version_info[
            "version"
        ]
    )

    release_name = (
        "YindaSurveySystem_"
        f"V{version}_test"
    )

    release_dir = (
        RELEASE_ROOT
        / release_name
    )

    zip_path = (
        RELEASE_ROOT
        / (
            release_name
            + ".zip"
        )
    )

    print()
    print(
        "=" * 60
    )
    print(
        version_info[
            "app_name"
        ]
    )
    print(
        "Test Release Builder"
    )
    print(
        f"Version: V{version}"
    )
    print(
        "Stage: "
        f"{version_info['stage']}"
    )
    print(
        "=" * 60
    )

    run_command(
        [
            str(
                VENV_PYTHON
            ),
            str(
                ROOT
                / "run_tests.py"
            ),
        ],
        label=(
            "Full regression tests"
        ),
    )

    print()
    print(
        "[1/5] Cleaning previous "
        "build outputs..."
    )

    remove_path(
        BUILD_DIR
    )
    remove_path(
        DIST_DIR
    )
    remove_path(
        release_dir
    )
    remove_path(
        zip_path
    )

    RELEASE_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_command(
        [
            str(
                VENV_PYTHON
            ),
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(
                SPEC_PATH
            ),
        ],
        label="PyInstaller",
    )

    exe_path = (
        DIST_APP
        / "YindaSurveySystem.exe"
    )

    if not exe_path.exists():
        raise RuntimeError(
            "PyInstaller finished but "
            "YindaSurveySystem.exe "
            "was not produced."
        )

    print()
    print(
        "[2/5] Assembling "
        "release directory..."
    )

    shutil.copytree(
        DIST_APP,
        release_dir,
    )

    target_templates = (
        release_dir
        / "templates"
    )

    if target_templates.exists():
        shutil.rmtree(
            target_templates
        )

    shutil.copytree(
        TEMPLATES_DIR,
        target_templates,
    )

    copied_docs = (
        copy_release_docs(
            release_dir=release_dir,
            version=version,
        )
    )

    write_release_info(
        release_dir=release_dir,
        version_info=version_info,
    )

    print()
    print(
        "[3/5] Verifying "
        "release directory..."
    )

    required_release = (
        (
            release_dir
            / "YindaSurveySystem.exe"
        ),
        (
            release_dir
            / "_internal"
        ),
        (
            release_dir
            / "templates"
            / "excel"
        ),
        (
            release_dir
            / "RELEASE_INFO.txt"
        ),
    )

    missing_release = [
        path
        for path
        in required_release
        if not path.exists()
    ]

    if missing_release:
        raise RuntimeError(
            "Release integrity check "
            "failed:\n"
            + "\n".join(
                f"- {path}"
                for path
                in missing_release
            )
        )

    if (
        release_dir
        / "local_data"
    ).exists():
        raise RuntimeError(
            "local_data unexpectedly "
            "exists in release directory. "
            "Build stopped to prevent "
            "shipping a development database."
        )

    print()
    print(
        "[4/5] Creating ZIP..."
    )

    archive_base = (
        RELEASE_ROOT
        / release_name
    )

    created_zip = Path(
        shutil.make_archive(
            str(
                archive_base
            ),
            "zip",
            root_dir=release_dir,
        )
    )

    if (
        not created_zip.exists()
        or created_zip.stat().st_size
        <= 0
    ):
        raise RuntimeError(
            "Release ZIP was not created "
            "correctly."
        )

    print()
    print(
        "[5/5] Writing ZIP "
        "SHA-256..."
    )

    checksum = (
        calculate_sha256(
            created_zip
        )
    )

    checksum_path = (
        RELEASE_ROOT
        / (
            created_zip.name
            + ".sha256.txt"
        )
    )

    checksum_path.write_text(
        (
            f"{checksum}  "
            f"{created_zip.name}\n"
        ),
        encoding="ascii",
        newline="\n",
    )

    print()
    print(
        "=" * 60
    )
    print(
        "[SUCCESS] Test release "
        "completed."
    )
    print(
        f"Directory: {release_dir}"
    )
    print(
        f"ZIP:       {created_zip}"
    )
    print(
        f"SHA256:    {checksum_path}"
    )

    if copied_docs:
        print(
            "Included release docs:"
        )

        for path in copied_docs:
            print(
                f"  - {path.name}"
            )
    else:
        print(
            "No version-specific "
            "client test docs were found; "
            "the build itself is still valid."
        )

    print(
        "=" * 60
    )


def check_only():
    check_required_paths()

    info = load_version_info()

    print(
        "[OK] Build environment "
        "preflight passed."
    )
    print(
        f"Version: V{info['version']}"
    )
    print(
        f"Stage:   {info['stage']}"
    )


def main():
    parser = (
        argparse.ArgumentParser()
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Only validate build "
            "prerequisites."
        ),
    )

    args = parser.parse_args()

    if args.check:
        check_only()
        return

    build_release()


if __name__ == "__main__":
    main()
