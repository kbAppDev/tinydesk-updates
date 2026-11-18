# Flare Tools - Image Compressor

A simple Windows desktop tool from Flare Fireplaces, using black, red and lime
green, rounded controls, and the shared Flare Tools identity.

Run **Flare-Image-Compressor-Setup-2.0.1.exe**. It installs without admin rights,
adds Image Compressor to the Flare Tools Start menu folder, and includes an
optional desktop shortcut and Windows uninstaller. Python is included.

1. Drop images or folders into the app, or choose **Add images** / **Add folder**.
2. Leave **Balanced** selected for everyday compression.
3. Click **Compress images**, then **Open folder** to find the copies.

Originals are never replaced. Matching names get numbered suffixes. Settings
are remembered. The default output folder is **Desktop / Flare Compressed
Images**, including redirected OneDrive desktops. More options holds WebP
conversion and optional resizing.

| Preset | JPEG / WebP quality | PNG |
| --- | --- | --- |
| Balanced | 82 | Keeps every pixel |
| Best quality | 92 | Keeps every pixel |
| Smallest | 68 | Up to 256 colors; exact transparency |

JPEG and WebP compression is lossy. Smallest may visibly reduce PNG color
detail. Same-format compression at original size never makes the copy larger:
already optimized files are copied unchanged when needed. Color profiles are
retained. Newly encoded images omit EXIF and ancillary metadata; unchanged
copies retain their original metadata. EXIF orientation is applied to newly
encoded images, so rotated images may swap width and height.

JPG, PNG and WebP keep their format. BMP and single-page TIFF become PNG.
Animated, multipage and over-50-megapixel images are skipped with an explanation.
Resizing keeps proportions and never upscales. Queue limit: 10,000 images.
Two background workers keep the interface responsive. Cancel stops remaining
work and keeps completed copies. Select a row for error details. Double-click
to open its completed copy or preview an unprocessed image. Remove and Clear
only change the queue.

Shortcuts: Ctrl+O add images; Ctrl+Shift+O add folder; Delete remove selected;
Ctrl+Enter compress; Esc cancel batch.

## Privacy and updates

Images are processed on your PC. No account, upload or internet connection is
needed for compression. Nothing starts automatically with Windows.
The app checks GitHub for updates daily when opened, or use Check for updates.
Downloaded installers must match their published SHA-256 checksum before they
can run. Installation requires a click and preserves settings.
Preferences and logs: `%LOCALAPPDATA%\Flare Tools\Image Compressor`.
Uninstalling leaves images and preferences intact. This release is unsigned;
Windows may show its standard publisher warning.

## Backups and builds

Extract the portable ZIP and run FlareImageCompressor.exe. Keep its _internal
folder beside it. The source ZIP is a rebuildable backup, including the suite
icon, palette and design notes. No user images, credentials or preferences.

Use Python 3.13 x64 and Inno Setup 6. Install requirements, then run:

```
python make_assets.py
python -m unittest discover -s tests -v
python tests/ui_smoke.py
python build_release.py
```

The release directory contains the installer, portable ZIP, source ZIP and
SHA256SUMS.txt. GitHub Actions can build, test and publish these artifacts.
For future versions, update VERSION in updater.py and AppVersion in
installer.iss together, then change release-request.txt to request that version.
Stable release tags use v2.0.1 format. The existing internal update repository,
kbAppDev/tinydesk-updates, retains its URL for continuity; the product is
branded Flare Tools throughout.

The shared design lives in flare_theme.py and FLARE-TOOLS-DESIGN.md. This
release does not modify the other installed tools.
