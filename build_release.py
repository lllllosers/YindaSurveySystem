from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import importlib.util
import shutil
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parent

EXPECTED_BRANCH = "release/v1.1.1"
EXPECTED_APP_NAME = "引大入秦工程现状调查采集系统"
EXPECTED_VERSION = "1.1.1"
EXPECTED_STAGE = "正式版"

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

RELEASE_NAME = (
    "YindaSurveySystem_"
    f"V{EXPECTED_VERSION}_"
    "Windows_x64"
)

FORBIDDEN_RUNTIME_NAMES = {
    "local_data",
    "data",
    "backup",
    "backups",
}

FORBIDDEN_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
}


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

    spec = (
        importlib.util
        .spec_from_file_location(
            "yinda_version",
            version_path,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            "Could not load src/version.py."
        )

    module = (
        importlib.util
        .module_from_spec(
            spec
        )
    )

    spec.loader.exec_module(
        module
    )

    return {
        "version": str(
            getattr(
                module,
                "APP_VERSION",
                "",
            )
        ).strip(),
        "stage": str(
            getattr(
                module,
                "APP_STAGE",
                "",
            )
        ).strip(),
        "app_name": str(
            getattr(
                module,
                "APP_NAME",
                "",
            )
        ).strip(),
    }


def run_git(
    *args,
    check=True,
):
    result = subprocess.run(
        [
            "git",
            *args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if (
        check
        and result.returncode != 0
    ):
        raise RuntimeError(
            "git "
            + " ".join(args)
            + " failed:\n"
            + result.stderr.strip()
        )

    return result.stdout.strip()


def check_required_paths():
    required = (
        VENV_PYTHON,
        SPEC_PATH,
        ICON_PATH,
        TEMPLATES_DIR,
        ROOT / "run_tests.py",
        ROOT / "src" / "version.py",
        ROOT / "README.md",
        ROOT / "docs" / "13_V1.1.1发布说明.md",
        ROOT / "docs" / "08_V1生产验收矩阵.md",
    )

    missing = [
        path
        for path in required
        if not path.exists()
    ]

    if missing:
        raise RuntimeError(
            "Required release inputs are missing:\n"
            + "\n".join(
                f"- {path}"
                for path in missing
            )
        )


def check_release_identity(
    version_info,
):
    errors = []

    if (
        version_info["app_name"]
        != EXPECTED_APP_NAME
    ):
        errors.append(
            "APP_NAME="
            + repr(
                version_info["app_name"]
            )
        )

    if (
        version_info["version"]
        != EXPECTED_VERSION
    ):
        errors.append(
            "APP_VERSION="
            + repr(
                version_info["version"]
            )
        )

    if (
        version_info["stage"]
        != EXPECTED_STAGE
    ):
        errors.append(
            "APP_STAGE="
            + repr(
                version_info["stage"]
            )
        )

    if errors:
        raise RuntimeError(
            "Release identity is not V1.1.1 final:\n"
            + "\n".join(
                f"- {item}"
                for item in errors
            )
        )


def check_git_state(
    *,
    require_clean,
):
    branch = run_git(
        "branch",
        "--show-current",
    )

    if branch != EXPECTED_BRANCH:
        raise RuntimeError(
            "Final release build must run from branch "
            f"{EXPECTED_BRANCH!r}; current={branch!r}."
        )

    tracked_status = run_git(
        "status",
        "--short",
        "--untracked-files=no",
        check=False,
    )

    if (
        require_clean
        and tracked_status
    ):
        raise RuntimeError(
            "Tracked working tree is not clean. "
            "Commit V1.1.1 release closeout changes before building:\n"
            + tracked_status
        )

    return {
        "branch": branch,
        "commit": run_git(
            "rev-parse",
            "--short",
            "HEAD",
        ),
        "tracked_clean": (
            not bool(
                tracked_status
            )
        ),
    }


def check_pyinstaller():
    result = subprocess.run(
        [
            str(
                VENV_PYTHON
            ),
            "-c",
            (
                "import PyInstaller; "
                "print(PyInstaller.__version__)"
            ),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "PyInstaller is not available in .venv:\n"
            + result.stderr.strip()
        )

    return result.stdout.strip()


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
    release_dir,
):
    copies = (
        (
            ROOT / "README.md",
            release_dir / "README.md",
        ),
        (
            ROOT
            / "docs"
            / "13_V1.1.1发布说明.md",
            release_dir
            / "V1.1.1_发布说明.md",
        ),
        (
            ROOT
            / "docs"
            / "08_V1生产验收矩阵.md",
            release_dir
            / "V1.1.1_生产验收记录.md",
        ),
    )

    copied = []

    for source, target in copies:
        shutil.copy2(
            source,
            target,
        )
        copied.append(
            target
        )

    return copied


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


def write_release_info(
    *,
    release_dir,
    version_info,
    git_info,
    pyinstaller_version,
):
    exe_path = (
        release_dir
        / "YindaSurveySystem.exe"
    )

    exe_sha256 = (
        calculate_sha256(
            exe_path
        )
        if exe_path.exists()
        else "unknown"
    )

    info_path = (
        release_dir
        / "RELEASE_INFO.txt"
    )

    text = (
        f"{version_info['app_name']}\n"
        "\n"
        f"Version=V{version_info['version']}\n"
        f"Stage={version_info['stage']}\n"
        f"Platform=Windows x64\n"
        f"BuildTime="
        f"{datetime.now().astimezone().isoformat(timespec='seconds')}\n"
        f"GitBranch={git_info['branch']}\n"
        f"GitCommit={git_info['commit']}\n"
        f"PyInstaller={pyinstaller_version}\n"
        f"ExecutableSHA256={exe_sha256}\n"
        "\n"
        "该目录为 V1.1.1 正式发布包。\n"
        "正式运行数据由程序在本目录下 local_data 中创建；"
        "发布包本身不预置开发数据库。\n"
    )

    info_path.write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )

    return info_path


def find_forbidden_runtime_artifacts(
    root,
):
    problems = []

    for path in root.rglob("*"):
        relative = (
            path.relative_to(
                root
            )
        )

        if any(
            part.lower()
            in FORBIDDEN_RUNTIME_NAMES
            for part in relative.parts
        ):
            problems.append(
                relative.as_posix()
            )
            continue

        if (
            path.is_file()
            and path.suffix.lower()
            in FORBIDDEN_SUFFIXES
        ):
            problems.append(
                relative.as_posix()
            )

    return sorted(
        set(
            problems
        )
    )


def verify_release_tree(
    release_dir,
):
    required = (
        release_dir
        / "YindaSurveySystem.exe",
        release_dir
        / "_internal",
        release_dir
        / "templates"
        / "excel",
        release_dir
        / "RELEASE_INFO.txt",
        release_dir
        / "README.md",
        release_dir
        / "V1.1.1_发布说明.md",
        release_dir
        / "V1.1.1_生产验收记录.md",
    )

    missing = [
        path
        for path in required
        if not path.exists()
    ]

    if missing:
        raise RuntimeError(
            "Release tree integrity check failed:\n"
            + "\n".join(
                f"- missing: {path}"
                for path in missing
            )
        )

    forbidden = (
        find_forbidden_runtime_artifacts(
            release_dir
        )
    )

    if forbidden:
        raise RuntimeError(
            "Release tree contains forbidden runtime/development data:\n"
            + "\n".join(
                f"- {item}"
                for item in forbidden
            )
        )


def verify_zip(
    zip_path,
):
    with zipfile.ZipFile(
        zip_path,
        "r",
    ) as archive:
        names = (
            archive.namelist()
        )

    required_names = {
        "YindaSurveySystem.exe",
        "RELEASE_INFO.txt",
        "README.md",
        "V1.1.1_发布说明.md",
        "V1.1.1_生产验收记录.md",
    }

    missing = [
        item
        for item in required_names
        if item not in names
    ]

    if missing:
        raise RuntimeError(
            "ZIP integrity check failed; missing entries:\n"
            + "\n".join(
                f"- {item}"
                for item in missing
            )
        )

    forbidden = []

    for name in names:
        parts = [
            part
            for part in name.split("/")
            if part
        ]

        if any(
            part.lower()
            in FORBIDDEN_RUNTIME_NAMES
            for part in parts
        ):
            forbidden.append(
                name
            )
            continue

        if (
            parts
            and Path(
                parts[-1]
            ).suffix.lower()
            in FORBIDDEN_SUFFIXES
        ):
            forbidden.append(
                name
            )

    if forbidden:
        raise RuntimeError(
            "ZIP contains forbidden runtime/development data:\n"
            + "\n".join(
                f"- {item}"
                for item in forbidden[:30]
            )
        )


def preflight(
    *,
    require_clean,
):
    check_required_paths()

    version_info = (
        load_version_info()
    )
    check_release_identity(
        version_info
    )

    git_info = (
        check_git_state(
            require_clean=(
                require_clean
            )
        )
    )

    pyinstaller_version = (
        check_pyinstaller()
    )

    return (
        version_info,
        git_info,
        pyinstaller_version,
    )


def build_release():
    (
        version_info,
        git_info,
        pyinstaller_version,
    ) = preflight(
        require_clean=True
    )

    release_dir = (
        RELEASE_ROOT
        / RELEASE_NAME
    )

    zip_path = (
        RELEASE_ROOT
        / (
            RELEASE_NAME
            + ".zip"
        )
    )

    checksum_path = (
        RELEASE_ROOT
        / (
            zip_path.name
            + ".sha256.txt"
        )
    )

    print()
    print(
        "=" * 72
    )
    print(
        version_info[
            "app_name"
        ]
    )
    print(
        "V1.1.1 Production Release Builder"
    )
    print(
        f"Version: V{version_info['version']}"
    )
    print(
        f"Stage:   {version_info['stage']}"
    )
    print(
        f"Commit:  {git_info['commit']}"
    )
    print(
        "=" * 72
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
        label="Full regression tests",
    )

    print()
    print(
        "[1/6] Cleaning build outputs..."
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
    remove_path(
        checksum_path
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
            "PyInstaller completed but "
            "YindaSurveySystem.exe was not produced."
        )

    print()
    print(
        "[2/6] Assembling final release directory..."
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
            release_dir
        )
    )

    write_release_info(
        release_dir=release_dir,
        version_info=version_info,
        git_info=git_info,
        pyinstaller_version=(
            pyinstaller_version
        ),
    )

    print()
    print(
        "[3/6] Verifying release directory..."
    )

    verify_release_tree(
        release_dir
    )

    print()
    print(
        "[4/6] Creating final ZIP..."
    )

    created_zip = Path(
        shutil.make_archive(
            str(
                RELEASE_ROOT
                / RELEASE_NAME
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
            "Final release ZIP was not created correctly."
        )

    print()
    print(
        "[5/6] Verifying ZIP contents..."
    )

    verify_zip(
        created_zip
    )

    print()
    print(
        "[6/6] Writing ZIP SHA-256..."
    )

    checksum = (
        calculate_sha256(
            created_zip
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
        "=" * 72
    )
    print(
        "[SUCCESS] V1.1.1 production release completed."
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
    print(
        "Included release docs:"
    )

    for path in copied_docs:
        print(
            f"  - {path.name}"
        )

    print()
    print(
        "NEXT: manually launch the EXE from the release directory, "
        "complete a clean first-run smoke test, close the app, "
        "and verify local_data is created only after launch."
    )
    print(
        "=" * 72
    )


def check_only():
    (
        version_info,
        git_info,
        pyinstaller_version,
    ) = preflight(
        require_clean=False
    )

    print(
        "[OK] Production release environment preflight passed."
    )
    print(
        f"App:       {version_info['app_name']}"
    )
    print(
        f"Version:   V{version_info['version']}"
    )
    print(
        f"Stage:     {version_info['stage']}"
    )
    print(
        f"Branch:    {git_info['branch']}"
    )
    print(
        f"Commit:    {git_info['commit']}"
    )
    print(
        "Tracked working tree clean: "
        + (
            "yes"
            if git_info[
                "tracked_clean"
            ]
            else "no"
        )
    )
    print(
        f"PyInstaller: {pyinstaller_version}"
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Validate production build prerequisites "
            "without building."
        ),
    )

    args = parser.parse_args()

    if args.check:
        check_only()
        return

    build_release()


if __name__ == "__main__":
    main()
