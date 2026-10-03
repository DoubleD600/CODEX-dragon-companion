from pathlib import Path
import sys
root = Path(SPECPATH)
a = Analysis([str(root / 'launcher.py')], pathex=[str(root / 'src')],
    binaries=[], datas=[(str(root / 'src/dragon_companion/assets'), 'dragon_companion/assets')],
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['tkinter', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtOpenGL'], noarchive=False)
if sys.platform == 'win32':
    # Qt uses Windows' ICU ABI; unrelated ICU builds on PATH have incompatible exports.
    a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower() not in
                  ('icuuc.dll', 'icudt78.dll', 'ucrtbase.dll') and
                  not Path(entry[0]).name.lower().startswith('api-ms-win-')]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='DragonCompanion',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, icon=str(root / 'src/dragon_companion/assets/app.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='DragonCompanion')
