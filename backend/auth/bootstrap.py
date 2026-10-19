"""One-time, non-destructive migration. Existing workspace files are never overwritten."""
import copy
import hashlib
import os
import secrets
import shutil

from backend.services.user_workspace import PROJECT_ROOT, write_json


def password_record(password):
    salt = secrets.token_hex(16)
    return {'salt': salt, 'hash': hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()}


def fresh_settings():
    return {
        'OPENAI_CONFIG': [{'name': 'OpenAI', 'api_key': '', 'base_url': 'https://api.openai.com/v1', 'models': []}],
        'selection': {'source': 'OpenAI', 'model': ''},
        'ASR_CONFIG': {'provider': 'soniox', 'fallback_provider': 'volcengine'},
        'SONIOX_CONFIG': {'api_key': '', 'api_host': 'https://api.soniox.com', 'ws_url': 'wss://stt-rt.soniox.com/transcribe-websocket', 'model': 'stt-rt-v5', 'language': 'zh', 'context': {}},
        'BYTEDANCE_ASR_CONFIG': {'app_key': '', 'access_key': '', 'url': 'wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream', 'segment_duration': 200},
        'VOLCENGINE_CONFIG': {'appid': '', 'token': '', 'cluster': 'volcengine_streaming_common', 'ws_url': 'wss://openspeech.bytedance.com/api/v2/asr', 'segment_duration': 200},
        'AUDIO_CONFIG': {'rate': 16000, 'channels': 1, 'chunk': 960, 'format': 8, 'language': 'zh-CN', 'max_duration_minutes': 5},
        'CHAT_CONTEXT_CONFIG': {'max_history_turns': 15, 'max_history_chars': 12000, 'include_assistant_history': False, 'debug_context': False, 'debug_context_full': False, 'debug_preview_chars': 160},
        'HOTKEY_CONFIG': {'toggle': 'ctrl+8', 'local_toggle': 'alt+e'},
        'DOUBAO_REALTIME': {'app_id': '', 'access_token': ''},
        'NOISE_REDUCTION': {'enabled': True, 'strength': 0.3},
        'DEFAULT_SESSION_CONFIG': {},
    }


def legacy_settings():
    import config
    import shlex
    settings = fresh_settings()
    for name in settings:
        if hasattr(config, name):
            settings[name] = copy.deepcopy(getattr(config, name))
    source = next((s for s in settings['OPENAI_CONFIG'] if s['name'] == config.DEFAULT_CONFIG_NAME), settings['OPENAI_CONFIG'][0])
    settings['selection'] = {'source': source['name'], 'model': next(iter(source['models']), '')}
    settings['DEFAULT_SESSION_CONFIG'] = {
        'source_name': '通义千问', 'models': ['qwen3.8-max', 'qwen3.7-plus'],
        'model_targets': [
            {'source_name': '通义千问', 'model': 'qwen3.8-max', 'reasoning_effort': 'none'},
            {'source_name': '通义千问', 'model': 'qwen3.7-plus', 'reasoning_effort': 'low'},
        ],
    }
    values = {}
    env = PROJECT_ROOT / '.env.local'
    if env.exists():
        for line in env.read_text().splitlines():
            key, sep, value = line.partition('=')
            if sep and key in ('DOUBAO_REALTIME_APP_ID', 'DOUBAO_REALTIME_ACCESS_TOKEN'):
                parts = shlex.split(value)
                values[key] = parts[0] if parts else ''
    settings['DOUBAO_REALTIME'] = {
        'app_id': os.environ.get('DOUBAO_REALTIME_APP_ID', values.get('DOUBAO_REALTIME_APP_ID', '')),
        'access_token': os.environ.get('DOUBAO_REALTIME_ACCESS_TOKEN', values.get('DOUBAO_REALTIME_ACCESS_TOKEN', '')),
    }
    settings['NOISE_REDUCTION'] = {'enabled': os.getenv('AUDIO_NOISE_REDUCTION', 'true').lower() not in ('0', 'false', 'off', 'no'), 'strength': float(os.getenv('AUDIO_NOISE_REDUCTION_STRENGTH', '0.3'))}
    return settings


def bootstrap_users():
    from backend.services.user_workspace import USERS_ROOT
    USERS_ROOT.mkdir(parents=True, exist_ok=True)
    for username in ('chenbo', 'chenshuai'):
        root = USERS_ROOT / username
        if root.exists():
            if not (root / 'account.json').exists() or not (root / 'settings.json').exists():
                raise RuntimeError(f'用户目录不完整，请检查后恢复: {root}')
            continue
        staging = USERS_ROOT / ('.' + username + '-initializing')
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(mode=0o700)
        settings = legacy_settings() if username == 'chenbo' else fresh_settings()
        write_json(staging / 'settings.json', settings)
        write_json(staging / 'account.json', {'username': username, 'password': password_record(username)})
        if username == 'chenbo':
            for name in ('sessions_index.json', 'storage', 'voices', 'screenshots', 'prompt_scenes.json'):
                source = PROJECT_ROOT / 'data' / name
                if source.is_dir():
                    shutil.copytree(source, staging / name)
                elif source.exists():
                    shutil.copy2(source, staging / name)
            lab = PROJECT_ROOT / 'prompt_lab'
            for name in ('prompts.json', 'background.json', 'questions.json', 'data'):
                source = lab / name
                target = staging / 'prompt_lab' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.is_dir():
                    shutil.copytree(source, target)
                elif source.exists():
                    shutil.copy2(source, target)
            for source, target in ((PROJECT_ROOT / 'logs' / 'chat_history', staging / 'logs' / 'chat_history'),
                                   (PROJECT_ROOT / 'backend' / 'logs', staging / 'logs' / 'legacy')):
                if source.exists():
                    shutil.copytree(source, target)
        for relative, default in (
            ('prompt_lab/prompts.json', []), ('prompt_lab/questions.json', []),
            ('prompt_lab/background.json', {'name': '个人背景', 'content': ''}),
            ('prompt_scenes.json', {'scenes': []}),
        ):
            if not (staging / relative).exists():
                write_json(staging / relative, default)
        for directory in ('voices', 'screenshots', 'prompt_lab/data/runs', 'prompt_lab/data/prompt_history', 'logs'):
            (staging / directory).mkdir(parents=True, exist_ok=True)
        staging.rename(root)
