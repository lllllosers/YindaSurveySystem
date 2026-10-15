# -*- mode: python ; coding: utf-8 -*-


from pathlib import Path
import sys
DESKTOP_ROOT = Path(SPECPATH)
REPO_ROOT = DESKTOP_ROOT.parent

# Conda-backed venvs hide conda-meta from PyInstaller. Collect only the DLLs
# required by the interpreter's stdlib extensions, leaving Qt on Windows ICU.
runtime_binaries = []
for name in ("sqlite3.dll", "libexpat.dll", "liblzma.dll", "LIBBZ2.dll",
             "libssl-3-x64.dll", "libcrypto-3-x64.dll"):
    for directory in (Path(sys.base_prefix) / "DLLs", Path(sys.base_prefix) / "Library" / "bin"):
        path = directory / name
        if path.is_file():
            runtime_binaries.append((str(path), "."))
            break

a = Analysis(
    [str(DESKTOP_ROOT / 'src/main.py')],
    pathex=[str(DESKTOP_ROOT / 'src'), str(REPO_ROOT)],
    binaries=runtime_binaries,
    datas=[(str(DESKTOP_ROOT / 'assets/app_icon.ico'), 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='YindaSurveySystem',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(DESKTOP_ROOT / 'assets/app_icon.ico')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='YindaSurveySystem',
)
