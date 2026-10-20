"""Best-effort old request reconstruction, strictly bounded by the target turn."""
from types import SimpleNamespace
from backend.api.models import SessionConfig, PromptScene
from backend.services.user_workspace import user_state, user_path
from backend.services.request_snapshots import question_for, save_request_snapshot
from backend.services.session_prompt import compose_session_system_prompt, render_session_user_prompt
from backend.services.chat_context import build_scoped_request
import json


def reconstruct_request(session_id, message_id):
    question_id = question_for(session_id, message_id)
    session = user_state().session_storage.load_session(session_id).model_copy(deep=True)
    index = next(i for i, m in enumerate(session.messages) if m.id == question_id)
    question = session.messages[index]
    selected = next(m for m in session.messages if m.id == message_id)
    answer = selected if selected.role == 'assistant' else next(
        (m for m in session.messages if m.role == 'assistant' and m.parent_id == question_id), None)
    notes = ['近似重建：使用现存会话配置和消息内容；历史上被编辑或删除的内容无法恢复。',
             '仅使用选中问题之前的用户消息及该问题本身，不包含之后的消息或历史 AI 回答。']
    config = session.session_config or SessionConfig(system_prompt=session.system_prompt)
    session.session_config = config
    if answer is not None:
        if answer.scene_name:
            if not config.active_scene or config.active_scene.name != answer.scene_name:
                path = user_path('prompt_scenes.json')
                catalog = json.loads(path.read_text()) if path.exists() else {}
                matches = [s for s in catalog.get('scenes', []) if s.get('name') == answer.scene_name]
                config.active_scene = PromptScene(**matches[0]) if len(matches) == 1 else None
                notes.append('根据原回答记录的场景名匹配现存场景规则，规则可能已被修改。' if len(matches) == 1 else
                             '原回答场景已缺失或名称不唯一，未套用其他场景；仅使用会话保存的系统提示词。')
        else:
            config.active_scene = None
            notes.append('原回答未记录场景，按默认场景重建。')
    else:
        notes.append('未找到原回答的场景记录，使用会话目前保存的场景。')
    if config.background_mode == 'shared' and not config.active_scene:
        notes.append('共享背景没有历史版本，使用目前保存的共享背景。')
    source = config.source_name or user_state().current_config.current_source
    model = next(iter(config.models), '') or user_state().current_config.current_model
    if config.model_targets:
        source, model = config.model_targets[0].source_name, config.model_targets[0].model
    if answer and answer.model_info:
        source, model = answer.model_info.provider, answer.model_info.name
    elif answer and answer.parallel_models:
        entry = answer.parallel_models[0]
        info = entry.get('model_info') or {}
        source = info.get('provider') or entry.get('source_name') or source
        model = info.get('name') or entry.get('model') or model
    from backend.api.routes import resolve_chat_context_config, trim_history_context, _multimodal_user_content
    limits = resolve_chat_context_config(config)
    # Slice by persisted position, never by timestamp: multiple turns may share a second.
    prior = [m for m in session.messages[:index] if m.role == 'user']
    prior = prior[-limits['max_history_turns']:]
    system = compose_session_system_prompt(session)
    history = [{'role': 'system', 'content': system}] if system else []
    history.extend({'role': 'user', 'content': m.content} for m in prior)
    history = trim_history_context(history, limits['max_history_chars'], model)
    messages = build_scoped_request(history, render_session_user_prompt(session, question.content))
    if question.attachments:
        messages[-1]['content'] = _multimodal_user_content(session.id, messages[-1]['content'], question.attachments)
    return save_request_snapshot(session_id, question_id, SimpleNamespace(name=source),
        {'model': model, 'messages': messages, 'temperature': config.temperature, 'top_p': config.top_p, 'stream': True},
        reconstruction={'mode': 'approximate', 'notes': notes, 'question_id': question_id,
                        'history_candidate_ids': [m.id for m in prior], 'scene_name': config.active_scene.name if config.active_scene else None})
