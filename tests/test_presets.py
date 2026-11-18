import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from presets import BUILTINS, CUSTOM, PresetStore, Profile


class PresetTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'settings' / 'presets.json'
        self.store = PresetStore(self.path)
        self.photo = Profile('Best quality', 'WebP', '2560 px')

    def test_new_user_and_builtin_selection(self):
        self.assertEqual(self.store.selected, 'Everyday')
        self.assertEqual(self.store.names, tuple(BUILTINS))
        self.store.select('Website images')
        restored = PresetStore(self.path)
        self.assertEqual(restored.selected, 'Website images')
        self.assertEqual(restored.current, BUILTINS['Website images'])

    def test_named_lifecycle_and_unicode(self):
        self.store.save('  Café menu  ', self.photo)
        restored = PresetStore(self.path)
        self.assertEqual(restored.selected, 'Café menu')
        self.assertEqual(restored.current, self.photo)
        restored.rename('CAFÉ MENU', 'Catalog')
        self.assertEqual(restored.selected, 'Catalog')
        restored.save('catalog', Profile(), overwrite=True)
        self.assertEqual(restored.selected, 'Catalog')
        self.assertEqual(restored.current, Profile())
        restored.delete('CATALOG')
        after_delete = PresetStore(self.path)
        self.assertEqual(after_delete.selected, 'Everyday')
        self.assertEqual(after_delete.user_names, ())

    def test_edited_settings_reopen_without_modifying_original(self):
        self.store.save('Storefront', self.photo)
        self.store.edit(BUILTINS['Email attachments'])
        restored = PresetStore(self.path)
        self.assertEqual(restored.selected, CUSTOM)
        self.assertEqual(restored.current, BUILTINS['Email attachments'])
        self.assertEqual(restored.select('Storefront'), self.photo)

    def test_existing_settings_migrate_and_new_settings_take_precedence(self):
        legacy = {'preset': 'Best quality', 'format': 'WebP', 'resize': '2560 px',
                  'output': 'C:/Images'}
        migrated = PresetStore(self.path, legacy)
        self.assertEqual(migrated.selected, CUSTOM)
        self.assertEqual(migrated.current, self.photo)
        migrated.save('My photos', self.photo)
        self.assertEqual(PresetStore(self.path, {}).selected, 'My photos')
        self.assertEqual(legacy['output'], 'C:/Images')

    def test_invalid_and_reserved_names_leave_file_intact(self):
        self.store.save('Cover', self.photo)
        original = self.path.read_bytes()
        for name in ('', 'x' * 49, 'Bad\nname', CUSTOM.upper(), ' EVERYDAY ', 'cover'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.store.save(name, Profile())
        with self.assertRaises(ValueError):
            self.store.rename('Cover', 'Website images')
        with self.assertRaises(ValueError):
            self.store.delete('Everyday')
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.store.selected, 'Cover')

    def test_multiple_instances_merge_changes(self):
        other = PresetStore(self.path)
        self.store.save('Cover', self.photo)
        other.save('Brochure', Profile())
        self.store.rename('Cover', 'Cover photos')
        after = PresetStore(self.path)
        self.assertEqual(after.user_names, ('Brochure', 'Cover photos'))
        self.assertEqual(after.selected, 'Brochure')

    def test_failed_save_rolls_back_and_cleans_up(self):
        self.store.save('Catalog', self.photo)
        original = self.path.read_bytes()
        with patch('presets.os.replace', side_effect=OSError('Read-only location')):
            with self.assertRaises(OSError):
                self.store.delete('Catalog')
        self.assertEqual(self.store.selected, 'Catalog')
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_malformed_profiles_recover_independently(self):
        self.path.parent.mkdir()
        self.path.write_text(json.dumps({'version': 1, 'profiles': {
            'Ad': {'quality': 'Best quality'}, 'Broken': {'resize': '123 px'},
            'WeBsite images': {}, 'Another broken': None}, 'selected': 'Ad'}))
        restored = PresetStore(self.path)
        self.assertEqual(restored.user_names, ('Ad',))
        self.assertEqual(restored.current, Profile('Best quality'))
        self.path.write_text('{malformed')
        self.assertEqual(PresetStore(self.path, {'resize': None}).current, Profile())


if __name__ == '__main__':
    unittest.main()
