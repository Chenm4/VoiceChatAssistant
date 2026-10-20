"""Replay frozen messages against another model without altering chat history."""
import asyncio
import copy
import json
import time
import uuid
from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel
from backend.api.models import ModelTarget
from backend.services.request_snapshots import directory, question_for, load_snapshot, messages_digest
from backend.services.user_workspace import user_state, write_json, workspace

router = APIRouter(prefix='/sessions', tags=['模型对比'])


class CompareRequest(BaseModel):
    snapshot_id: str
    target: ModelTarget


def results_dir(session_id, question_id):
    return directory(session_id, question_id) / 'comparisons'


@router.get('/{session_id}/messages/{message_id}/comparisons')
async def list_comparisons(session_id: str, message_id: str):
    question = question_for(session_id, message_id)
    snapshots = []
    for path in directory(session_id, question).glob('*.json'):
        record = json.loads(path.read_text())
        params = record['parameters']
        snapshots.append({'id': record['id'], 'created_at': record['created_at'], 'source': record['source'],
                          'model': params['model'], 'message_count': len(params['messages']),
                          'messages_sha256': record['messages_sha256']})
    results = [json.loads(p.read_text()) for p in results_dir(session_id, question).glob('*.json')]
    for result in results:
        if result['status'] == 'pending' and result['id'] not in workspace().tasks:
            result.update(status='interrupted', error='服务已重启，任务中断；请重新对比。')
            write_json(results_dir(session_id, question) / (result['id'] + '.json'), result)
    return {'snapshots': sorted(snapshots, key=lambda x: x['created_at'], reverse=True),
            'results': sorted(results, key=lambda x: x['created_at'], reverse=True)}


@router.get('/{session_id}/messages/{message_id}/comparisons/snapshots/{snapshot_id}')
async def preview_snapshot(session_id: str, message_id: str, snapshot_id: str):
    question = question_for(session_id, message_id)
    return load_snapshot(session_id, question, snapshot_id)


async def run_comparison(session_id, question, record, source, params):
    path = results_dir(session_id, question) / (record['id'] + '.json')
    started = time.monotonic()
    try:
        async with AsyncOpenAI(api_key=source.api_key, base_url=source.base_url, timeout=120, max_retries=0) as client:
            response = await client.chat.completions.create(**params)
        answer = response.choices[0].message
        from backend.api.routes import provider_reasoning_text
        record.update(status='success', content=answer.content or '', reasoning_content=provider_reasoning_text(answer),
                      usage=response.usage.model_dump() if response.usage else None)
    except Exception as error:
        # Do not persist provider error bodies, which may echo credentials or inputs.
        record.update(status='error', error=f'模型调用失败（{type(error).__name__}，HTTP {getattr(error, "status_code", "—")}），可重新对比。')
    finally:
        record['latency_ms'] = int((time.monotonic() - started) * 1000)
        write_json(path, record)


@router.post('/{session_id}/messages/{message_id}/comparisons', status_code=202)
async def create_comparison(session_id: str, message_id: str, body: CompareRequest):
    question = question_for(session_id, message_id)
    snapshot = load_snapshot(session_id, question, body.snapshot_id)
    source = next((s for s in user_state().config_sources if s.name == body.target.source_name), None)
    if not source or body.target.model not in source.models or not source.api_key:
        raise HTTPException(400, '请先配置目标模型及 API Key')
    from backend.api.routes import get_chat_completion_extra_params
    # Freeze messages verbatim: no trimming, prompt reload, or attachment reread.
    params = {key: copy.deepcopy(snapshot['parameters'][key]) for key in ('messages', 'temperature', 'top_p') if key in snapshot['parameters']}
    params.update(model=body.target.model, stream=False,
                  **get_chat_completion_extra_params(source, body.target.model, body.target.reasoning_effort))
    record = {'id': uuid.uuid4().hex, 'snapshot_id': snapshot['id'], 'created_at': time.time(),
              'target': body.target.model_dump(), 'status': 'pending', 'content': '',
              'messages_sha256': messages_digest(params['messages']),
              'parameters': {k: v for k, v in params.items() if k != 'messages'}}
    write_json(results_dir(session_id, question) / (record['id'] + '.json'), record)
    task = asyncio.create_task(run_comparison(session_id, question, record, source, params))
    # Keep the task alive if the browser closes the dialog or navigates away.
    tasks = workspace().tasks
    tasks[record['id']] = task
    task.add_done_callback(lambda _: tasks.pop(record['id'], None))
    return record
