import json
import secrets
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.auth import session_store as store
from backend.auth.session import TTL
from backend.services import user_workspace as users


class PersistentLoginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        patcher = patch.object(users, 'USERS_ROOT', self.root)
        patcher.start(); self.addCleanup(patcher.stop)
        users.write_json(self.root / 'alice/account.json', {'password': {'hash': 'test-hash', 'salt': 'test-salt'}})
        self.token = secrets.token_urlsafe(32)

    def test_survives_new_process_without_storing_bearer_token(self):
        self.assertEqual(TTL, 90 * 24 * 3600)
        store.save_session(self.token, 'alice', time.time() + TTL)
        path = store.session_path(self.token)
        self.assertNotIn(self.token, path.read_text())
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        script = '''import sys,json
from pathlib import Path
from backend.services import user_workspace as users
from backend.auth.session_store import load_session
value=json.load(sys.stdin)
users.USERS_ROOT=Path(value['root'])
assert load_session(value['token'])['username']=='alice'
print('ok')
'''
        result = subprocess.run([sys.executable, '-c', script], input=json.dumps({'root': str(self.root), 'token': self.token}), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'ok')

    def test_expiry_logout_and_password_change_revoke(self):
        store.save_session(self.token, 'alice', time.time() - 1)
        self.assertIsNone(store.load_session(self.token))
        store.save_session(self.token, 'alice', time.time() + TTL)
        store.revoke_session(self.token)
        self.assertIsNone(store.load_session(self.token))
        store.save_session(self.token, 'alice', time.time() + TTL)
        users.write_json(self.root / 'alice/account.json', {'password': {'hash': 'new-hash'}})
        self.assertIsNone(store.load_session(self.token))
        self.assertIsNone(store.load_session('../invalid'))
