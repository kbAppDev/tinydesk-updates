"""Exercise our own app in isolation without changing user preferences."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
temporary = tempfile.TemporaryDirectory()
base = Path(temporary.name)
os.environ['FLARE_IMAGE_DATA_DIR'] = str(base / 'preferences')
from PIL import Image
from app import TinyDeskApp

app = TinyDeskApp()
app.withdraw()
app.output = base / 'output'
app.report_callback_exception = lambda *args: (_ for _ in ()).throw(args[1])

def until(predicate, timeout=20):
    deadline = time.monotonic() + timeout
    while not predicate():
        app.update()
        if time.monotonic() > deadline:
            raise AssertionError('App did not finish before the timeout.')
        time.sleep(.01)
    app.update()

try:
    source = base / 'source'
    source.mkdir()
    Image.effect_noise((900, 600), 40).convert('RGB').save(source / 'sample.jpg', quality=98)
    Image.new('RGBA', (900,600), (255,0,0,140)).save(source / 'transparent.png', compress_level=0)
    (source / 'broken.png').write_bytes(b'not an image')
    app.import_paths([str(source)])
    until(lambda: not app.importing)
    assert len(app.files) == 3
    assert app.compress_button.cget('fg_color') == '#99CC00'
    app.start_batch()
    until(lambda: not app.busy)
    assert app.run_ok == 2, app.results
    assert app.run_errors == 1
    assert all(path.exists() for path in [source/'sample.jpg', source/'transparent.png'])
    assert len(list(app.output.glob('*'))) == 2
    app.clear()
    app.update()
    assert not app.files
    app.save_settings()
    assert (base/'preferences/settings.json').exists()
    print(json.dumps({'startup':'passed', 'import':'passed', 'batch':'2 saved / 1 expected error',
                      'clear':'passed', 'preferences':'passed', 'primary_color':app.compress_button.cget('fg_color')}))
finally:
    app.destroy()
    temporary.cleanup()
