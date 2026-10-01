# -*- mode: python ; coding: utf-8 -*-


from pathlib import Path
DESKTOP_ROOT = Path(SPECPATH)
REPO_ROOT = DESKTOP_ROOT.parent

a = Analysis(
    [str(DESKTOP_ROOT / 'src/main.py')],
    pathex=[str(DESKTOP_ROOT / 'src'), str(REPO_ROOT)],
    binaries=[],
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
