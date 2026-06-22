# -*- mode: python ; coding: utf-8 -*-

from datetime import datetime
from pathlib import Path


build_time = datetime.now().astimezone()
build_info = Path(SPECPATH) / 'backend' / 'build_info.py'
build_info.write_text(
    f"BUILD_DATETIME = '{build_time:%d/%m/%Y %H:%M}'\n"
    f"BUILD_VERSION = '{build_time:%Y%m%d%H%M%S}'\n",
    encoding='utf-8',
)


a = Analysis(
    ['backend\\medsoft_app.py'],
    pathex=[],
    binaries=[],
    datas=[('templates', 'templates'), ('static', 'static')],
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
    a.binaries,
    a.datas,
    [],
    name='medsoft_app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
