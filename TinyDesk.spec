# One-folder packaging starts immediately without extracting on every launch.
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

datas = [('assets/FlareTools.ico', 'assets'), ('README.md', '.'), ('FLARE-TOOLS-DESIGN.md', '.'), ('assets/FlareTools.png', 'assets'), ('THIRD-PARTY-NOTICES.txt', '.')]
datas += collect_data_files('tkinterdnd2', includes=['tkdnd/win-x64/*'])
datas += collect_data_files('customtkinter')
datas += copy_metadata('Pillow') + copy_metadata('tkinterdnd2')
a = Analysis(['app.py'], pathex=[], binaries=[], datas=datas, hiddenimports=['PIL.ImageTk'],
             hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['PySide6', 'PyQt5', 'PyQt6', 'numpy', 'matplotlib', 'scipy', 'pandas', 'IPython'],
             noarchive=False, optimize=1)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='FlareImageCompressor', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon=['assets/FlareTools.ico'])
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='FlareImageCompressor')
