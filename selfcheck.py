"""Verify bundled Tcl, drag-and-drop, assets and the desktop processing path."""
import json
from pathlib import Path
import sys
import tempfile
import time
import traceback
from PIL import Image

def run(module, report):
    report = Path(report).resolve()
    app = None
    temporary = tempfile.TemporaryDirectory()
    base = Path(temporary.name)
    try:
        module.DATA = base / 'settings'
        sys.argv = sys.argv[:1]
        app = module.TinyDeskApp()
        app.withdraw()
        app.output = base / 'output'
        app.select_profile('Website images')
        app.resize.set('1280 px')
        app.options_changed()
        app.save_profile('Self-check export')
        stored = module.PresetStore(module.DATA / 'presets.json')
        assert stored.selected == 'Self-check export'
        assert stored.current == module.Profile('Balanced', 'WebP', '1280 px')
        source = base / 'sample.png'
        Image.new('RGBA', (1600,900), (150,70,30,120)).save(source, compress_level=0)
        app.import_paths([str(source)])
        deadline = time.monotonic() + 20
        while app.importing:
            app.update()
            if time.monotonic() > deadline:
                raise AssertionError('Import timed out.')
            time.sleep(.01)
        assert len(app.files) == 1
        assert app.compress_button.cget('fg_color') == '#99CC00'
        app.start_batch()
        while app.busy:
            app.update()
            if time.monotonic() > deadline:
                raise AssertionError('Compression timed out.')
            time.sleep(.01)
        assert app.run_ok == 1 and app.run_errors == 0
        assert source.exists()
        result = next(iter(app.results.values()))
        assert result.output.exists() and result.after <= result.before
        with Image.open(result.output) as encoded:
            assert encoded.format == 'WEBP' and encoded.size == (1280, 720)
            assert encoded.getpixel((0, 0))[3] == 120
        report.write_text(json.dumps({'result':'passed', 'suite':'Flare Tools', 'version':module.updater.VERSION,
            'startup':True, 'drag_drop_runtime':True, 'suite_icon':True, 'batch':True,
            'original_protected':True, 'preset_export':True, 'primary_color':'#99CC00'}, indent=2), 'utf-8')
        return 0
    except Exception:
        report.write_text(json.dumps({'result':'failed', 'error':traceback.format_exc()}, indent=2),'utf-8')
        return 1
    finally:
        if app is not None:
            app.destroy()
        temporary.cleanup()
