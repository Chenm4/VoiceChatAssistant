import json
from pathlib import Path
import tempfile
import unittest
from scripts.sync_user_settings import sync
from backend.services.user_workspace import write_json


class SyncSettingsTests(unittest.TestCase):
    def test_backups_and_accounts_preserved_and_stale_override_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.json'
            settings = {'selection': {'source': 'test', 'model': 'model'},
                        'OPENAI_CONFIG': [{'name': 'test', 'api_key': 'test-key',
                                           'base_url': 'https://example.test', 'models': ['model']}],
                        'api_config': {'api_key': 'stale'}}
            write_json(source, settings)
            for name in ('alice', 'bob'):
                write_json(root / 'users' / name / 'account.json', {'password': 'unchanged'})
                write_json(root / 'users' / name / 'settings.json', {'old': name})
            sync(source, root / 'users', root / 'backups')
            backup = next((root / 'backups').iterdir())
            for name in ('alice', 'bob'):
                user = root / 'users' / name
                self.assertEqual(json.loads((user / 'account.json').read_text()), {'password': 'unchanged'})
                self.assertEqual(json.loads((backup / name / 'settings.json').read_text()), {'old': name})
                self.assertEqual(json.loads((user / 'settings.json').read_text())['api_config']['api_key'], 'test-key')
                self.assertEqual((user / 'settings.json').stat().st_mode & 0o777, 0o600)
