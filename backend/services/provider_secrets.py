"""Keep the Xiaomi key in the ignored local environment file."""
import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[2] / '.env.local'


def load_xiaomi_key():
    if os.environ.get('XIAOMI_API_KEY'):
        return os.environ['XIAOMI_API_KEY']
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
            if line.startswith('XIAOMI_API_KEY='):
                return line.partition('=')[2].strip().strip('\"\'')
    return ''


def save_xiaomi_key(key):
    lines = ENV_PATH.read_text(encoding='utf-8').splitlines() if ENV_PATH.exists() else []
    lines = [line for line in lines if not line.startswith('XIAOMI_API_KEY=')]
    # API keys are single-line ASCII credentials, never executable shell content.
    import shlex
    lines.append('XIAOMI_API_KEY=' + shlex.quote(key))
    ENV_PATH.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    ENV_PATH.chmod(0o600)
    os.environ['XIAOMI_API_KEY'] = key
