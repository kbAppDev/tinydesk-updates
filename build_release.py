"""Build a self-contained Windows release. Run from a clean source checkout."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import zipfile

from updater import VERSION

ROOT = Path(__file__).parent.resolve()
os.chdir(ROOT)
release = ROOT / 'release'
release.mkdir(exist_ok=True)
subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', 'TinyDesk.spec'], check=True)
licenses = ROOT / 'dist' / 'FlareImageCompressor' / '_internal' / 'licenses'
licenses.mkdir(exist_ok=True)
for package in ('Pillow', 'tkinterdnd2', 'pyinstaller', 'customtkinter', 'darkdetect'):
    dist = importlib.metadata.distribution(package)
    for entry in dist.files or []:
        if 'license' in str(entry).lower() or 'copying' in str(entry).lower():
            path = Path(dist.locate_file(entry))
            if path.is_file():
                destination = licenses / package / Path(str(entry))
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
for path in (Path(sys.base_prefix) / 'LICENSE.txt', Path(sys.base_prefix) / 'tcl' / 'license.terms'):
    if path.is_file():
        shutil.copy2(path, licenses / (path.parent.name + '-' + path.name))
compiler_candidates = [shutil.which('ISCC.exe'),
    str(Path(os.environ['LOCALAPPDATA']) / 'Programs/Inno Setup 6/ISCC.exe'),
    str(Path.home() / 'AppData/Local/Programs/Inno Setup 6/ISCC.exe'), 'C:/Program Files (x86)/Inno Setup 6/ISCC.exe', 'C:/Program Files/Inno Setup 6/ISCC.exe']
compiler = next((path for path in compiler_candidates if path and Path(path).is_file()), None)
if not compiler:
    raise SystemExit('Install Inno Setup 6 before building the installer.')
subprocess.run([compiler, 'installer.iss'], check=True)
portable = release / f'Flare-Image-Compressor-{VERSION}-portable.zip'
with zipfile.ZipFile(portable, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for path in sorted((ROOT / 'dist' / 'FlareImageCompressor').rglob('*')):
        if path.is_file():
            archive.write(path, path.relative_to(ROOT / 'dist'))
source = release / f'Flare-Image-Compressor-{VERSION}-source.zip'
source_files = [
    'app.py', 'ui.py', 'engine.py', 'presets.py', 'thumbnails.py', 'flare_theme.py', 'updater.py',
    'selfcheck.py',
    'build_release.py', 'make_assets.py', 'TinyDesk.spec', 'installer.iss', 'version-info.txt',
    'requirements.txt', 'release-request.txt', '.github/workflows/release.yml',
    '.github/scripts/verify-installer-upgrade.ps1', 'docs/image-compressor.png',
    'README.md', 'FLARE-TOOLS-DESIGN.md', 'RELEASE-NOTES.md', 'THIRD-PARTY-NOTICES.txt',
    'assets/FlareTools.ico', 'assets/FlareTools.png', 'assets/FlareTools.svg',
    'tests/ui_smoke.py', 'tests/preset_workflow.py',
]
with zipfile.ZipFile(source, 'w', zipfile.ZIP_DEFLATED) as archive:
    paths = [ROOT / name for name in source_files] + sorted((ROOT / 'tests').glob('test_*.py'))
    for path in paths:
        archive.write(path, Path('Flare-Image-Compressor') / path.relative_to(ROOT))
assets = [release / f'Flare-Image-Compressor-Setup-{VERSION}.exe', portable, source]
(release / 'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name + '\n' for path in assets), 'utf-8')
print(json.dumps([{'path': str(path), 'bytes': path.stat().st_size} for path in assets], indent=2))
