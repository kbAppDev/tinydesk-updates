"""Local image processing. No UI or network dependencies."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import tempfile
import threading
import warnings

from PIL import Image, ImageChops, ImageOps

SUPPORTED = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}
Image.MAX_IMAGE_PIXELS = 50_000_000


@dataclass(frozen=True)
class Options:
    preset: str = 'Balanced'
    format: str = 'Keep format'
    max_edge: int = 0


@dataclass(frozen=True)
class Result:
    source: Path
    output: Path | None
    before: int
    after: int
    status: str
    error: str = ''


def human_bytes(value: int) -> str:
    size = float(value)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024 or unit == 'GB':
            return f'{size:.1f} {unit}' if unit != 'B' else f'{int(size)} B'
        size /= 1024


def discover(paths, cancel: threading.Event | None = None):
    """Walk folders without following links; callers deduplicate canonical paths."""
    for value in paths:
        path = Path(value)
        if cancel and cancel.is_set():
            return
        if path.is_dir() and not path.is_symlink():
            for root, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = sorted(d for d in dirs if not Path(root, d).is_symlink())
                for name in sorted(files):
                    if cancel and cancel.is_set():
                        return
                    candidate = Path(root, name)
                    if candidate.suffix.lower() in SUPPORTED and not candidate.is_symlink():
                        yield candidate.resolve()
        elif path.is_file() and path.suffix.lower() in SUPPORTED:
            yield path.resolve()


def publish_unique(temp: Path, output_dir: Path, name: str) -> Path:
    """On Windows rename is atomic and never replaces an existing destination."""
    stem, suffix = Path(name).stem, Path(name).suffix
    for index in range(100_000):
        destination = output_dir / (name if index == 0 else f'{stem} ({index}){suffix}')
        try:
            # Hard links atomically refuse collisions on Windows and POSIX.
            os.link(temp, destination)
            temp.unlink()
            return destination
        except FileExistsError:
            continue
        except OSError:
            # Exclusive creation also protects originals on filesystems without links.
            try:
                with destination.open('xb') as target, temp.open('rb') as source:
                    try:
                        shutil.copyfileobj(source, target, 1024 * 1024)
                    except BaseException:
                        target.close()
                        destination.unlink(missing_ok=True)
                        raise
                temp.unlink()
                return destination
            except FileExistsError:
                continue
    raise OSError('Too many matching filenames in the output folder.')


def compress(source: Path, output_dir: Path, options: Options, cancel: threading.Event) -> Result:
    before = 0
    temp = None
    try:
        if cancel.is_set():
            return Result(source, None, 0, 0, 'Canceled')
        before = source.stat().st_size
        output_dir.mkdir(parents=True, exist_ok=True)
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(source) as opened:
                if getattr(opened, 'n_frames', 1) != 1:
                    raise ValueError('Animated or multipage image: skipped to preserve every frame.')
                original_format = opened.format
                if opened.width * opened.height > Image.MAX_IMAGE_PIXELS:
                    raise ValueError('Image exceeds 50 megapixels. Resize it before adding it here.')
                icc = opened.info.get('icc_profile')
                # Draft decoding avoids full-size JPEG decoding when resizing.
                if options.max_edge and original_format == 'JPEG':
                    opened.draft(opened.mode, (options.max_edge, options.max_edge))
                image = ImageOps.exif_transpose(opened)
                if options.max_edge:
                    image.thumbnail((options.max_edge, options.max_edge), Image.Resampling.LANCZOS, reducing_gap=3.0)
                image.load()
                if cancel.is_set():
                    return Result(source, None, before, 0, 'Canceled')
                target_format = 'WEBP' if options.format == 'WebP' else original_format
                if target_format not in {'JPEG', 'PNG', 'WEBP'}:
                    target_format = 'PNG'
                suffix = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}[target_format]
                if target_format == original_format and source.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'}:
                    suffix = source.suffix
                fd, temporary = tempfile.mkstemp(prefix='.tinydesk-', suffix=suffix, dir=output_dir)
                os.close(fd)
                temp = Path(temporary)
                save_options = {'icc_profile': icc} if icc else {}
                quality = {'Best quality': 92, 'Balanced': 82, 'Smallest': 68}[options.preset]
                if target_format == 'JPEG':
                    if image.mode not in {'RGB', 'L', 'CMYK'}:
                        image = image.convert('RGB')
                    image.save(temp, 'JPEG', quality=quality, optimize=True, progressive=True,
                               subsampling=0 if options.preset == 'Best quality' else 2, **save_options)
                elif target_format == 'WEBP':
                    if image.mode not in {'RGB', 'RGBA'}:
                        image = image.convert('RGBA' if 'A' in image.getbands() or 'transparency' in image.info else 'RGB')
                    image.save(temp, 'WEBP', quality=quality, method=3, exact=True, **save_options)
                else:
                    # Balanced and Best quality preserve PNG pixels. Smaller PNGs
                    # explicitly trades color detail for size, preserving alpha exactly.
                    if options.preset == 'Smallest' and image.mode in {'RGB', 'RGBA'}:
                        quantized = image.quantize(colors=256, method=Image.Quantize.FASTOCTREE,
                                                   dither=Image.Dither.NONE)
                        if image.mode != 'RGBA' or ImageChops.difference(
                            image.getchannel('A'), quantized.convert('RGBA').getchannel('A')).getbbox() is None:
                            image = quantized
                    image.save(temp, 'PNG', compress_level=6, **save_options)
        if cancel.is_set():
            return Result(source, None, before, 0, 'Canceled')
        after = temp.stat().st_size
        status = 'Compressed'
        # Same-format compression never produces a larger copy. Metadata in an
        # already optimized original is retained when using this exact-copy path.
        if after >= before and target_format == original_format and not options.max_edge:
            shutil.copyfile(source, temp)
            after = before
            status = 'Already optimized'
        destination = publish_unique(temp, output_dir, source.stem + suffix)
        temp = None
        return Result(source, destination, before, after, status)
    except Exception as error:
        return Result(source, None, before, 0, 'Error', str(error))
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
