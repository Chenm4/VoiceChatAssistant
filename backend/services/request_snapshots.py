"""Immutable provider inputs, private to the authenticated workspace."""
import copy
import hashlib
import json
import re
import time
import uuid
from fastapi import HTTPException
from backend.services.user_workspace import user_path, user_state, write_json


def checked_id(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
        raise HTTPException(400, '无效标识')
    return value


def question_for(session_id, message_id):
    session = user_state().session_storage.load_session(checked_id(session_id))
    if not session:
        raise HTTPException(404, '会话不存在')
    message = next((m for m in session.messages if m.id == message_id), None)
    if not message:
        raise HTTPException(404, '消息不存在')
    question_id = message.id if message.role == 'user' else message.parent_id
    if not question_id or not any(m.id == question_id and m.role == 'user' for m in session.messages):
        raise HTTPException(409, '未找到对应问题')
    return checked_id(question_id)


def directory(session_id, question_id):
    return user_path(f'request_snapshots/{checked_id(session_id)}/{checked_id(question_id)}')


def messages_digest(messages):
    return hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def save_request_snapshot(session_id, question_id, source, params, reconstruction=None):
    # Only SDK request arguments, never provider credentials. Keep image data intact.
    parameters = copy.deepcopy(params)
    record = {'id': uuid.uuid4().hex, 'created_at': time.time(), 'source': source.name,
              'parameters': parameters, 'messages_sha256': messages_digest(parameters['messages'])}
    if reconstruction is not None:
        record['reconstruction'] = reconstruction
    write_json(directory(session_id, question_id) / (record['id'] + '.json'), record)
    return record


def load_snapshot(session_id, question_id, snapshot_id):
    path = directory(session_id, question_id) / (checked_id(snapshot_id) + '.json')
    if not path.exists():
        raise HTTPException(404, '原始请求快照不存在，无法保证历史一致')
    record = json.loads(path.read_text())
    if messages_digest(record['parameters']['messages']) != record['messages_sha256']:
        raise HTTPException(409, '请求快照校验失败')
    return record
