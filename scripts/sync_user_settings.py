"""Explicit offline settings sync; stop the service before applying."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.services.user_workspace import write_json


def sync(source, users_root, backup_root):
    settings = json.loads(source.read_text())
    selected = settings['selection']
    provider = next(s for s in settings['OPENAI_CONFIG'] if s['name'] == selected['source'])
    if not provider.get('api_key') or selected['model'] not in provider['models']:
        raise ValueError('Source must have a key and a valid selected model')
    # Remove stale per-user overrides by deriving these from the source selection.
    settings['api_config'] = {k: provider[k] for k in ('api_key', 'base_url')}
    settings['api_config']['model'] = selected['model']
    targets = sorted(p for p in users_root.glob('*/settings.json') if (p.parent / 'account.json').is_file())
    if not targets:
        raise ValueError('No existing user accounts found')
    originals = {p: json.loads(p.read_text()) for p in targets}
    backup = backup_root / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup.mkdir(parents=True, mode=0o700)
    os.chmod(backup, 0o700)
    for path, original in originals.items():
        write_json(backup / path.parent.name / 'settings.json', original)
    for path in targets:
        write_json(path, settings)
        assert json.loads(path.read_text()) == settings
    print(json.dumps({'users': [p.parent.name for p in targets], 'backup': str(backup)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--users-root', type=Path, required=True)
    parser.add_argument('--backup-root', type=Path, required=True)
    args = parser.parse_args()
    sync(args.source, args.users_root, args.backup_root)
