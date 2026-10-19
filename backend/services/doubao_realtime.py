"""Seeduplex 3.0 JSON protocol; credentials stay on the server.

The legacy console's provisioned resource is volc.service_type.10074.
Reference: https://www.volcengine.com/docs/6561/2549778
"""
import base64
import json
import os
import shlex
from pathlib import Path
from uuid import uuid4

ENDPOINT = 'wss://openspeech.bytedance.com/api/v3/duplex/realtime/dialogue'
RESOURCE_ID = 'volc.service_type.10074'
MODEL = '1.2.6.1'
MODEL_NAME = 'Seeduplex 3.0'
ENV_PATH = Path(__file__).resolve().parents[2] / '.env.local'


def credentials():
    values = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
            key, sep, value = line.partition('=')
            if sep and key in ('DOUBAO_REALTIME_APP_ID', 'DOUBAO_REALTIME_ACCESS_TOKEN'):
                parts = shlex.split(value)
                values[key] = parts[0] if parts else ''
    return tuple(os.environ.get(key, values.get(key, '')) for key in
                 ('DOUBAO_REALTIME_APP_ID', 'DOUBAO_REALTIME_ACCESS_TOKEN'))


def auth_headers(connect_id):
    app_id, token = credentials()
    if not app_id or not token:
        raise ValueError('请在后端 .env.local 配置豆包实时语音凭据')
    return {'X-Api-App-ID': app_id, 'X-Api-Access-Key': token,
            'X-Api-Resource-Id': RESOURCE_ID,
            'X-Api-App-Key': 'PlgvMymc7f3tQnJ6', 'X-Api-Connect-Id': connect_id,
            'X-Api-Request-Id': connect_id}


def encode_event(event_type, **fields):
    return json.dumps({'type': event_type, 'event_id': str(uuid4()), **fields}, ensure_ascii=False)


def decode_event(raw):
    event = json.loads(raw)
    if not isinstance(event, dict) or not isinstance(event.get('type'), str):
        raise ValueError('无效的上游事件')
    return event


def session_payload(options):
    # Upstream requires audio.output even for our text-only UI. Never relay its audio.
    return {'model': MODEL, 'instructions': options.system_role,
            'audio': {'input': {'format': {'type': 'pcm', 'rate': 16000}},
                      'output': {'voice': 'zh_female_vv_jupiter_bigtts',
                                 'format': {'type': 'pcm_s16le', 'rate': 24000}}}}


def encode_audio(pcm):
    return encode_event('input_audio_buffer.append', audio=base64.b64encode(pcm).decode('ascii'))


def normalize_event(event):
    """Keep browser events stable while adapting the upstream JSON protocol."""
    kind = event['type']
    if kind.startswith('response.output_audio.'):
        return None
    mapping = {
        'conversation.item.input_audio_transcription.started': 450,
        'conversation.item.input_audio_transcription.delta': 451,
        'conversation.item.input_audio_transcription.completed': 459,
        'response.output_text.delta': 550,
        'response.output_text.done': 559,
        'response.done': 154,
        'session.closed': 152,
    }
    data = dict(event)
    if kind == 'response.output_text.delta':
        data['content'] = event.get('delta', '')
        data['reply_id'] = event.get('response_id', '')
    if kind == 'conversation.item.input_audio_transcription.delta':
        data = {'delta': event.get('delta', ''), 'item_id': event.get('item_id', '')}
    return {'type': 'event', 'event': mapping.get(kind), 'upstream_type': kind, 'data': data}
