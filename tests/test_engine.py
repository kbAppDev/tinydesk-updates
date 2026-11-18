import hashlib
from pathlib import Path
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageChops
from engine import Options, compress, discover


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.out = self.root / 'output'
        self.cancel = threading.Event()

    def tearDown(self):
        self.temp.cleanup()

    def make(self, name='sample.png', mode='RGB', size=(640, 480)):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.effect_noise(size, 30).convert(mode)
        if mode == 'RGBA':
            image.putalpha(Image.linear_gradient('L').resize(size))
        image.save(path, compress_level=0) if path.suffix == '.png' else image.save(path)
        return path

    def test_jpeg_original_unchanged_dimensions_and_smaller(self):
        source = self.make('photo.jpg')
        digest = hashlib.sha256(source.read_bytes()).digest()
        result = compress(source, self.out, Options(), self.cancel)
        self.assertFalse(result.error)
        self.assertLessEqual(result.after, result.before)
        self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), digest)
        with Image.open(result.output) as image:
            self.assertEqual(image.size, (640, 480))

    def test_png_balanced_is_pixel_exact(self):
        source = self.make()
        result = compress(source, self.out, Options(), self.cancel)
        with Image.open(source) as original, Image.open(result.output) as output:
            self.assertIsNone(ImageChops.difference(original, output).getbbox())

    def test_rgba_preserves_alpha_in_every_preset(self):
        source = self.make(mode='RGBA')
        for preset in ('Balanced', 'Best quality', 'Smallest'):
            result = compress(source, self.out, Options(preset=preset), self.cancel)
            self.assertFalse(result.error)
            with Image.open(source) as original, Image.open(result.output) as output:
                self.assertIsNone(ImageChops.difference(original.getchannel('A'), output.convert('RGBA').getchannel('A')).getbbox())

    def test_duplicate_names_and_same_output_directory_never_overwrite(self):
        first = self.make('one/same.png')
        second = self.make('two/same.png')
        self.out.mkdir()
        existing = self.out / 'same.png'
        existing.write_bytes(b'keep this file')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda path: compress(path, self.out, Options(), self.cancel), [first, second]))
        self.assertEqual(existing.read_bytes(), b'keep this file')
        self.assertEqual(len({result.output for result in results}), 2)
        original = first.read_bytes()
        result = compress(first, first.parent, Options(), self.cancel)
        self.assertNotEqual(result.output, first)
        self.assertEqual(first.read_bytes(), original)

    def test_resize_aspect_ratio_no_upscale(self):
        source = self.make('photo.jpg', size=(1600, 1000))
        result = compress(source, self.out, Options(max_edge=800), self.cancel)
        with Image.open(result.output) as image:
            self.assertEqual(image.size, (800, 500))
        result = compress(source, self.out, Options(max_edge=2560), self.cancel)
        with Image.open(result.output) as image:
            self.assertEqual(image.size, (1600, 1000))

    def test_webp_conversion_preserves_alpha(self):
        source = self.make(mode='RGBA')
        result = compress(source, self.out, Options(format='WebP'), self.cancel)
        self.assertFalse(result.error)
        with Image.open(source) as original, Image.open(result.output) as output:
            self.assertEqual(output.format, 'WEBP')
            self.assertIsNone(ImageChops.difference(original.getchannel('A'), output.getchannel('A')).getbbox())

    def test_corrupt_file_does_not_leave_partial_output(self):
        source = self.root / 'broken.png'
        source.write_bytes(b'not an image')
        result = compress(source, self.out, Options(), self.cancel)
        self.assertEqual(result.status, 'Error')
        self.assertFalse(list(self.out.glob('*')))

    def test_cancellation_produces_no_output(self):
        source = self.make()
        self.cancel.set()
        result = compress(source, self.out, Options(), self.cancel)
        self.assertEqual(result.status, 'Canceled')
        self.assertIsNone(result.output)

    def test_animated_file_is_not_flattened(self):
        source = self.root / 'animated.webp'
        Image.new('RGB', (20, 20), 'red').save(source, save_all=True, append_images=[Image.new('RGB', (20, 20), 'blue')], duration=100)
        result = compress(source, self.out, Options(), self.cancel)
        self.assertIn('Animated', result.error)

    def test_exif_orientation_is_applied(self):
        source = self.root / 'rotated.jpg'
        exif = Image.Exif()
        exif[274] = 6
        Image.new('RGB', (80, 40), 'red').save(source, exif=exif)
        result = compress(source, self.out, Options(max_edge=60), self.cancel)
        with Image.open(result.output) as image:
            self.assertEqual(image.size, (30, 60))
            self.assertNotIn(274, image.getexif())

    def test_paletted_transparency_and_icc_are_kept(self):
        source = self.root / 'palette.png'
        image = Image.new('P', (80, 80), 0)
        image.putpalette([255, 0, 0, 0, 255, 0] + [0] * 762)
        image.save(source, transparency=0, icc_profile=b'test-profile')
        result = compress(source, self.out, Options(), self.cancel)
        with Image.open(result.output) as image:
            self.assertEqual(image.convert('RGBA').getpixel((0, 0))[3], 0)
            self.assertEqual(image.info['icc_profile'], b'test-profile')

    def test_bmp_converts_to_png(self):
        source = self.make('source.bmp')
        result = compress(source, self.out, Options(), self.cancel)
        self.assertEqual(result.output.suffix, '.png')

    def test_discovery_finds_nested_images(self):
        first = self.make('folder/a.png')
        second = self.make('folder/nested/b.jpg')
        (first.parent / 'text.txt').write_text('skip')
        self.assertEqual(set(discover([first.parent])), {first, second})


if __name__ == '__main__':
    unittest.main()
