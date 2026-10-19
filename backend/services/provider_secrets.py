"""Legacy Xiaomi-key reader, used only during first-time chenbo migration."""
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
