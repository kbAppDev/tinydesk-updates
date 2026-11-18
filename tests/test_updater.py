import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import updater


class UpdateTests(unittest.TestCase):
    def setUp(self):
        major, minor, patch_number = updater.version_tuple(updater.VERSION)
        self.next_version = f'{major}.{minor}.{patch_number + 1}'

    def fixture(self, version=None, checksum=True):
        version = version or self.next_version
        prefix = f'https://github.com/{updater.REPOSITORY}/releases/download/v{version}/'
        assets = [{'name': f'Flare-Image-Compressor-Setup-{version}.exe', 'browser_download_url': prefix + f'Flare-Image-Compressor-Setup-{version}.exe'}]
        if checksum:
            assets.append({'name': 'SHA256SUMS.txt', 'browser_download_url': prefix + 'SHA256SUMS.txt'})
        return json.dumps({'tag_name': 'v' + version, 'assets': assets}).encode()

    def test_current_version(self):
        with patch.object(updater, 'read_url', return_value=self.fixture(updater.VERSION)):
            self.assertIsNone(updater.check())

    def test_new_version_with_hash(self):
        expected_name = f'Flare-Image-Compressor-Setup-{self.next_version}.exe'
        hashes = f'{"a" * 64}  {expected_name}\n'.encode()
        with patch.object(updater, 'read_url', side_effect=[self.fixture(), hashes]):
            info = updater.check()
            self.assertEqual(info['version'], self.next_version)
            self.assertEqual(info['sha256'], 'a' * 64)

    def test_previous_install_recognizes_this_release(self):
        version = updater.VERSION
        name = f'Flare-Image-Compressor-Setup-{version}.exe'
        hashes = f'{"b" * 64}  {name}\n'.encode()
        with patch.object(updater, 'VERSION', '2.0.1'), patch.object(
            updater, 'read_url', side_effect=[self.fixture(version), hashes]
        ):
            self.assertEqual(updater.check()['name'], name)

    def test_missing_hash_refused(self):
        with patch.object(updater, 'read_url', return_value=self.fixture(checksum=False)):
            with self.assertRaises(ValueError):
                updater.check()

    def test_prerelease_version_refused(self):
        with self.assertRaises(ValueError):
            updater.version_tuple(f'v{updater.VERSION}-beta')

    def test_failed_checksum_never_installed(self):
        import io
        class Response(io.BytesIO):
            headers = {'Content-Length': '7'}
        info = {'name': 'installer.exe', 'url': 'https://github.com/test', 'sha256': '0' * 64}
        with tempfile.TemporaryDirectory() as folder, patch('urllib.request.urlopen', return_value=Response(b'example')):
            with self.assertRaises(ValueError):
                updater.download(info, Path(folder))
            self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
