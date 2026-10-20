"""Persistent, revocable login sessions; raw bearer tokens never reach disk."""
import hashlib
import json
import re
import time
from backend.services.user_workspace import write_json


def sessions_root():
    from backend.services.user_workspace import USERS_ROOT
    return USERS_ROOT / '.login_sessions'


def session_path(token):
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token or ''):
        return None
    return sessions_root() / (hashlib.sha256(token.encode()).hexdigest() + '.json')


def account_version(username):
    from backend.services.user_workspace import USERS_ROOT
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,31}', username):
        raise ValueError('Invalid username')
    account = json.loads((USERS_ROOT / username / 'account.json').read_text())
    return hashlib.sha256(json.dumps(account['password'], sort_keys=True).encode()).hexdigest()


def save_session(token, username, expires):
    path = session_path(token)
    if path is None:
        raise ValueError('Invalid session token')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_json(path, {'username': username, 'expires': expires, 'account_version': account_version(username)})


def revoke_session(token):
    path = session_path(token)
    if path is not None:
        path.unlink(missing_ok=True)


def load_session(token):
    path = session_path(token)
    if path is None:
        return None
    try:
        record = json.loads(path.read_text())
        if record['expires'] <= time.time() or record['account_version'] != account_version(record['username']):
            revoke_session(token)
            return None
        return record
    except (OSError, ValueError, KeyError, TypeError):
        return None
