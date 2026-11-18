"""Check saved presets across real restarts and through the desktop batch engine."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
NAME = 'Dealer web'
WEB = ('Smallest', 'WebP', '1280 px')
ORIGINAL = ('Best quality', 'Keep format', 'Original size')


def controls(window):
    return window.preset.get(), window.format.get(), window.resize.get()


def until(window, predicate):
    deadline = time.monotonic() + 20
    while not predicate():
        window.update()
        assert time.monotonic() < deadline, 'Timed out waiting for the desktop batch.'
        time.sleep(0.01)


def create_preset(window):
    assert controls(window) == ORIGINAL  # Settings from the preceding release.
    window.preset.set(WEB[0])
    window.format.set(WEB[1])
    window.resize.set(WEB[2])
    window.options_changed()
    window.save_profile('Dealer site')
    window.rename_profile('Dealer site', NAME)
    window.select_profile('Product photos')
    assert controls(window) == ORIGINAL
    window.select_profile(NAME)
    assert controls(window) == WEB
    assert 'Dealer site' not in window.profile_picker.cget('values')


def run_batch(window, expected):
    window.start_batch()
    until(window, lambda: not window.busy)
    assert window.run_ok == len(expected) and not window.run_errors, window.results
    outputs = {}
    for result in window.results.values():
        assert result.output.parent == window.output
        with Image.open(result.output) as image:
            assert (image.format, image.size) == expected[result.source.name]
            if result.source.suffix == '.png':
                assert image.convert('RGBA').getpixel((0, 0))[3] == 112
        outputs[result.source.name] = result.output
    return outputs


def use_preset(window, base):
    assert window.profile_var.get() == NAME and controls(window) == WEB
    assert NAME in window.profile_picker.cget('values')
    assert window.output == base / 'output'
    source = base / 'source'
    window.import_paths([str(source)])
    until(window, lambda: not window.importing)
    assert len(window.files) == 2
    web_outputs = {name: ('WEBP', (1280, 853)) for name in ('photo.jpg', 'cutout.png')}
    outputs = run_batch(window, web_outputs)
    small_photo_bytes = outputs['photo.jpg'].stat().st_size
    window.preset.set('Best quality')
    window.options_changed()
    window.save_profile(NAME, overwrite=True)
    outputs = run_batch(window, web_outputs)
    assert outputs['photo.jpg'].stat().st_size > small_photo_bytes, 'The quality change did not reach the encoder.'
    window.select_profile('Product photos')
    run_batch(window, {'photo.jpg': ('JPEG', (2304, 1536)), 'cutout.png': ('PNG', (2304, 1536))})
    window.select_profile(NAME)
    window.delete_profile(NAME)
    assert NAME not in window.profile_picker.cget('values')


def run_window(phase, base):
    sys.path.insert(0, str(ROOT))
    from app import TinyDeskApp

    # The GUI accepts file paths on its command line. Keep the test phase private.
    sys.argv = sys.argv[:1]
    with patch.object(TinyDeskApp, 'check_updates'):
        window = TinyDeskApp()
        window.withdraw()
        try:
            if phase == 'create':
                create_preset(window)
            elif phase == 'use':
                use_preset(window, base)
            else:
                assert window.profile_var.get() == 'Everyday'
                assert NAME not in window.profile_picker.cget('values')
                assert controls(window) == ('Balanced', 'Keep format', 'Original size')
        finally:
            window.on_close()


def main():
    if len(sys.argv) == 2:
        run_window(sys.argv[1], Path(os.environ['FLARE_IMAGE_DATA_DIR']).parent)
        return
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        data = base / 'preferences'
        data.mkdir()
        settings = {'preset': ORIGINAL[0], 'format': ORIGINAL[1], 'resize': ORIGINAL[2],
                    'output': str(base / 'output')}
        (data / 'settings.json').write_text(json.dumps(settings), encoding='utf-8')
        source = base / 'source'
        source.mkdir()
        Image.effect_noise((2304, 1536), 40).convert('RGB').save(source / 'photo.jpg', quality=96)
        Image.new('RGBA', (2304, 1536), (40, 100, 50, 112)).save(source / 'cutout.png')
        originals = {file: file.read_bytes() for file in source.iterdir()}
        env = dict(os.environ, FLARE_IMAGE_DATA_DIR=str(data))
        for phase in ('create', 'use', 'reopen'):
            subprocess.run([sys.executable, str(Path(__file__).resolve()), phase], env=env, check=True, timeout=45)
        assert all(file.read_bytes() == contents for file, contents in originals.items())
    print('Preset migration, save, rename, update, delete, restart and JPEG/PNG/WebP batches passed.')


if __name__ == '__main__':
    main()
