"""
API 路由定义
"""

import asyncio
import base64
import hashlib
import io
import json
import os
import re
import sys
import uuid
import wave
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.api.models import (
    ConfigModel,
    SceneCatalog,
    ConfigSource,
    ConfigList,
    ChatRequest, 
    ChatResponse,
    RecordingResponse,
    RecordingStartRequest,
    ChatMessage,
    Session,
    SessionList,
    SessionIndex,
    SessionIndexList,
    SessionConfig,
    MessageUpdateRequest,
    BatchDeleteRequest,
    RegenerateMessageRequest,
    ModelInfo,
    MessageAttachment,
    TokenUsage
)
from backend.services.audio_recorder import AudioRecorder
from backend.services.voice_recognizer import VoiceRecognizer
from backend.services.streaming_asr import StreamingASR
from backend.services.chat_context import build_scoped_request
from backend.services.token_budget import count_tokens, newest_tokens
from backend.services.session_prompt import (
    compose_session_system_prompt,
    create_default_session_config,
    render_session_user_prompt,
)
from backend.services.session_storage import session_storage
from backend.utils.logger import get_api_logger
from backend.utils.chat_logger import (
    log_model_interaction,
    log_error
)
from backend.utils.id_generator import generate_session_id
from openai import OpenAI, AsyncOpenAI
import time

# 导入配置
try:
    from config import OPENAI_CONFIG, DEFAULT_CONFIG_NAME, CHAT_CONTEXT_CONFIG
except ImportError:
    OPENAI_CONFIG = [
        {
            "name": "OpenAI",
            "api_key": "",
            "models": ["gpt-3.5-turbo", "gpt-4"],
            "base_url": "https://api.openai.com/v1"
        }
    ]
    DEFAULT_CONFIG_NAME = "OpenAI"
    CHAT_CONTEXT_CONFIG = {
        "max_history_turns": 15,
        "max_history_chars": 12000,
        "include_assistant_history": False,
        "debug_context": True,
        "debug_context_full": False,
        "debug_preview_chars": 160,
    }

logger = get_api_logger()
VOICE_DIR = Path(__file__).parent.parent.parent / "data" / "voices"
SCREENSHOT_DIR = Path(__file__).parent.parent.parent / "data" / "screenshots"
MAX_SCREENSHOT_BYTES = 8 * 1024 * 1024
SCREENSHOT_MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def _content_text_length(content: Any) -> int:
    """Count textual request content without expanding image data URLs in logs."""
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(
            len(str(part.get("text", "")))
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return 0


def _content_log_preview(content: Any, preview_chars: int, show_full: bool) -> str:
    if isinstance(content, list):
        text_parts = [
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        image_count = sum(
            1 for part in content
            if isinstance(part, dict) and part.get("type") == "image_url"
        )
        content = " ".join(text_parts)
        image_suffix = f" [images={image_count}]" if image_count else ""
    else:
        content = str(content or "")
        image_suffix = ""
    shown = content if show_full else content[:preview_chars]
    if not show_full and len(content) > preview_chars:
        shown += "..."
    return shown.replace("\n", "\\n") + image_suffix


def _redact_request_secrets(value: Any) -> Any:
    """Remove credentials while preserving the complete request structure."""
    if isinstance(value, dict):
        if value.get("type") == "image_url" and isinstance(value.get("image_url"), dict):
            image_url = value["image_url"]
            url = image_url.get("url", "")
            if isinstance(url, str) and url.startswith("data:") and ";base64," in url:
                header, encoded = url.split(",", 1)
                image_bytes = base64.b64decode(encoded)
                return _redact_request_secrets({
                    **{key: _redact_request_secrets(item) for key, item in value.items() if key != "image_url"},
                    "image_url": {
                        **{key: _redact_request_secrets(item) for key, item in image_url.items() if key != "url"},
                        "url": {
                            "type": "image",
                            "mime_type": header[5:].split(";", 1)[0],
                            "sha256": hashlib.sha256(image_bytes).hexdigest(),
                        },
                    },
                })
        return {
            key: ("[REDACTED]" if re.search(
                r"api[_-]?key|authorization|access[_-]?token|secret|password",
                str(key), re.IGNORECASE
            ) else _redact_request_secrets(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_request_secrets(item) for item in value]
    return value


def log_provider_request(source: ConfigSource, params: Dict[str, Any]) -> Dict[str, Any]:
    """Log all Chat Completions parameters immediately before the SDK call."""
    payload = _redact_request_secrets({
        "provider": source.name,
        "base_url": source.base_url,
        "endpoint": "chat.completions.create",
        "parameters": params,
    })
    logger.info("📤 [供应商请求参数]\n%s", json.dumps(
        payload, ensure_ascii=False, indent=2, default=str
    ))
    return payload


def log_model_request_context(
    model: str,
    messages: List[Dict[str, str]],
    label: str = "聊天",
    context_settings: Optional[Dict[str, Any]] = None,
):
    """Print a safe, compact summary of the exact messages sent to a model.

    The API logger already writes to the terminal and to ``backend/logs``.
    Keep the default output bounded so a long prompt does not flood the
    console; set ``CHAT_DEBUG_CONTEXT_FULL=1`` when full message bodies are
    needed for a local debugging session.
    """
    if not CHAT_CONTEXT_CONFIG.get("debug_context", True):
        return

    total_chars = sum(_content_text_length(message.get("content", "")) for message in messages)
    user_count = sum(1 for message in messages if message.get("role") == "user")
    assistant_count = sum(1 for message in messages if message.get("role") == "assistant")
    system_count = sum(1 for message in messages if message.get("role") == "system")
    token_model = model.split("::")[-1]
    text_tokens = sum(
        count_tokens(str(message.get("content", "")), token_model)
        if isinstance(message.get("content", ""), str)
        else sum(count_tokens(str(part.get("text", "")), token_model)
                 for part in message.get("content", [])
                 if isinstance(part, dict) and part.get("type") == "text")
        for message in messages
    )
    context_settings = context_settings or CHAT_CONTEXT_CONFIG
    logger.info(
        f"📨 [模型请求上下文] label={label}, model={model}, "
        f"messages={len(messages)} (system={system_count}, user={user_count}, "
        f"assistant={assistant_count}), chars={total_chars}, "
        f"text_tokens={text_tokens} (不含图片), "
        f"max_history_turns={context_settings.get('max_history_turns', 15)}, "
        f"max_history_tokens={context_settings.get('max_history_chars', 12000)}, "
        f"include_assistant={context_settings.get('include_assistant_history', False)}"
    )

    preview_chars = CHAT_CONTEXT_CONFIG.get("debug_preview_chars", 160)
    show_full = CHAT_CONTEXT_CONFIG.get("debug_context_full", False)
    for index, message in enumerate(messages, 1):
        role = message.get("role", "unknown")
        content = message.get("content", "")
        shown = _content_log_preview(content, preview_chars, show_full)
        logger.info(
            f"   [{label}] {index:02d} role={role}, "
            f"chars={_content_text_length(content)}: {shown}"
        )


def resolve_chat_context_config(session_config: Optional[SessionConfig]) -> Dict[str, Any]:
    """Resolve global context defaults with optional per-session overrides."""
    settings = {
        "max_history_turns": CHAT_CONTEXT_CONFIG.get("max_history_turns", 15),
        "max_history_chars": CHAT_CONTEXT_CONFIG.get("max_history_chars", 12000),
        "include_assistant_history": CHAT_CONTEXT_CONFIG.get(
            "include_assistant_history", False
        ),
    }
    if session_config is not None:
        if session_config.max_history_turns is not None:
            settings["max_history_turns"] = session_config.max_history_turns
        if session_config.max_history_chars is not None:
            settings["max_history_chars"] = session_config.max_history_chars
        if session_config.include_assistant_history is not None:
            settings["include_assistant_history"] = session_config.include_assistant_history
    return settings


def trim_history_context(
    messages: List[Dict[str, str]],
    max_tokens: int,
    model: str = "",
) -> List[Dict[str, str]]:
    """Trim historical API messages to a bounded token budget.

    System messages are always retained. Older user turns are removed first;
    when one remaining message is itself larger than the budget, keep its
    newest tail rather than dropping the whole conversation.
    """
    if max_tokens <= 0:
        return messages

    system_messages = [
        message for message in messages if message.get("role") == "system"
    ]
    history_messages = [
        message for message in messages if message.get("role") != "system"
    ]

    # Group a user message with any immediately following assistant messages,
    # so dropping old context never leaves an orphaned assistant turn.
    turns = []
    current_turn = []
    for message in history_messages:
        if message.get("role") == "user" and current_turn:
            turns.append(current_turn)
            current_turn = []
        current_turn.append(message)
    if current_turn:
        turns.append(current_turn)

    def turns_tokens() -> int:
        return sum(
            count_tokens(str(message.get("content", "")), model)
            for turn in turns
            for message in turn
        )

    # Drop complete oldest turns first, but always retain the newest turn.
    while len(turns) > 1 and turns_tokens() > max_tokens:
        turns.pop(0)

    if turns and turns_tokens() > max_tokens:
        # If the newest turn itself is too large, preserve the user question
        # first and use any remaining budget for assistant text. This keeps a
        # meaningful latest question even when it is very long.
        turn = turns[0]
        user_index = next(
            (index for index, message in enumerate(turn)
             if message.get("role") == "user"),
            0,
        )
        user_message = turn[user_index]
        user_content = str(user_message.get("content", ""))
        kept_user = newest_tokens(user_content, max_tokens, model)
        remaining = max_tokens - count_tokens(kept_user, model)
        bounded_turn = [{**user_message, "content": kept_user}]
        if remaining > 0:
            for message in turn[user_index + 1:]:
                content = str(message.get("content", ""))
                if not content:
                    continue
                kept = newest_tokens(content, remaining, model)
                bounded_turn.append({**message, "content": kept})
                remaining -= count_tokens(kept, model)
                if remaining <= 0:
                    break
        turns[0] = bounded_turn

    return system_messages + [message for turn in turns for message in turn]

# 创建路由器
router = APIRouter()
# Invalidate outstanding generations when a newer request/config takes over.
generation_epochs: Dict[str, str] = {}

# 全局服务实例
audio_recorder = AudioRecorder()
voice_recognizer = VoiceRecognizer()
streaming_asr = None  # 实时流式识别实例（每次录音时使用）
streaming_asr_pool = None  # 预热实例池（启动时创建）
openai_client = None

# 从 config.py 读取初始配置
config_sources = [ConfigSource(**source) for source in OPENAI_CONFIG]

# 找到默认配置源
default_source = next((s for s in config_sources if s.name == DEFAULT_CONFIG_NAME), config_sources[0])
current_config = ConfigList(
    sources=config_sources,
    current_source=default_source.name,
    current_model=default_source.models[0] if default_source.models else "gpt-3.5-turbo"
)


# 将配置写回 config.py 文件
def save_config_to_file():
    """将当前配置源列表写回 config.py 文件"""
    try:
        config_path = Path(__file__).parent.parent.parent / "config.py"
        
        # 读取原文件内容
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 构建新的 OPENAI_CONFIG
        config_list = []
        for source in config_sources:
            config_dict = {
                "name": source.name,
                "api_key": source.api_key,
                "models": source.models,
                "base_url": source.base_url
            }
            config_list.append(config_dict)
        
        # 格式化为 Python 代码
        config_lines = []
        config_lines.append("OPENAI_CONFIG = [")
        for i, source in enumerate(config_sources):
            config_lines.append("    {")
            config_lines.append(f'        "name": "{source.name}",')
            # 如果 API key 为空，添加注释
            if "api.xiaomimimo.com" in source.base_url:
                from backend.services.provider_secrets import save_xiaomi_key
                save_xiaomi_key(source.api_key)
                config_lines.append('        "api_key": load_xiaomi_key(),')
            elif source.api_key:
                config_lines.append(f'        "api_key": "{source.api_key}",')
            else:
                config_lines.append(f'        "api_key": "",  # 填写您的 {source.name} API Key')
            config_lines.append(f'        "models": {json.dumps(source.models, ensure_ascii=False)},')
            config_lines.append(f'        "base_url": "{source.base_url}"')
            if i < len(config_sources) - 1:
                config_lines.append("    },")
            else:
                config_lines.append("    }")
        config_lines.append("]")
        new_config_block = "\n".join(config_lines)
        
        # 使用正则表达式替换 OPENAI_CONFIG 部分
        pattern = r'OPENAI_CONFIG = \[[\s\S]*?\n\]'
        new_content = re.sub(pattern, new_config_block, content)
        
        # 写回文件
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        logger.info(f"配置已保存到 config.py")
        return True
    except Exception as e:
        logger.error(f"保存配置到文件失败: {e}", exc_info=True)
        return False

# 向后兼容的单一配置
api_config = ConfigModel(
    api_key=default_source.api_key,
    model=current_config.current_model,
    base_url=default_source.base_url
)


async def iterate_provider_stream(stream):
    """Keep synchronous SDK reads off the event loop so scene changes stay responsive."""
    sentinel = object()
    try:
        while True:
            chunk = await asyncio.to_thread(next, stream, sentinel)
            if chunk is sentinel:
                break
            yield chunk
    finally:
        close = getattr(stream, "close", None)
        if close:
            await asyncio.to_thread(close)


def get_chat_completion_extra_params(
    source: Optional[ConfigSource],
    model: str,
    reasoning_effort: str = "none",
) -> Dict[str, Any]:
    """Return provider-specific Chat Completions options."""
    source_name = (source.name if source else "").lower()
    base_url = (source.base_url if source else api_config.base_url).lower()
    model_name = (model or "").lower()
    effort = reasoning_effort if reasoning_effort in {
        "none", "minimal", "low", "medium", "high", "xhigh"
    } else "none"
    
    if "api.xiaomimimo.com" in base_url:
        return {"extra_body": {"thinking": {"type": "disabled" if effort == "none" else "enabled"}}}

    # Legacy 'none' defaults now mean minimal on OpenRouter, never disabled.
    # Resolve the gateway before model families (including Qwen routed through it).
    if source_name == "openrouter" or "openrouter.ai" in base_url:
        if effort == "none":
            effort = "minimal"
        return {"extra_body": {"reasoning": {"effort": effort}}}

    if (
        source_name == "qwen"
        or "dashscope.aliyuncs.com" in base_url
        or model_name.startswith("qwen")
    ):
        if effort == "none":
            return {"extra_body": {"enable_thinking": False}}
        # openai 1.x forwards extra_body at the JSON top level. DashScope's
        # OpenAI-compatible endpoint accepts reasoning_effort there.
        return {"extra_body": {"reasoning_effort": effort}}

    openai_reasoning_model = bool(re.match(r"^(gpt-[56]|o[134](?:-|$))", model_name))
    if (
        (source_name == "openai" or "api.openai.com" in base_url)
        and openai_reasoning_model
    ):
        return {"extra_body": {"reasoning_effort": effort}}
    
    return {}


def resolve_model_targets(
    session_config: Optional[SessionConfig],
    requested_model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Resolve every selected model to its own API source and credentials."""
    requested_targets = []
    if requested_model:
        if "::" in requested_model:
            requested_source, model_name = requested_model.split("::", 1)
            configured_target = next((
                target for target in (session_config.model_targets if session_config else [])
                if target.source_name == requested_source and target.model == model_name
            ), None)
            requested_targets = [(
                requested_source,
                model_name,
                configured_target.reasoning_effort if configured_target else "none",
            )]
        else:
            matching_source = next(
                (source for source in config_sources if requested_model in source.models),
                None,
            )
            if not matching_source:
                raise HTTPException(
                    status_code=400,
                    detail=f"找不到模型 {requested_model} 对应的配置源",
                )
            configured_target = next((
                target for target in (session_config.model_targets if session_config else [])
                if target.source_name == matching_source.name and target.model == requested_model
            ), None)
            requested_targets = [(
                matching_source.name,
                requested_model,
                configured_target.reasoning_effort if configured_target else "none",
            )]
    elif session_config and session_config.model_targets:
        requested_targets = [
            (target.source_name, target.model, target.reasoning_effort)
            for target in session_config.model_targets
        ]
    elif session_config and session_config.models:
        legacy_source = session_config.source_name or current_config.current_source
        requested_targets = [
            (legacy_source, model_name, "none") for model_name in session_config.models
        ]
    else:
        requested_targets = [(current_config.current_source, api_config.model, "none")]

    resolved = []
    seen = set()
    for source_name, model_name, reasoning_effort in requested_targets:
        key = f"{source_name}::{model_name}"
        if key in seen:
            continue
        source = next((item for item in config_sources if item.name == source_name), None)
        if not source:
            raise HTTPException(status_code=400, detail=f"配置源 {source_name} 不存在")
        if model_name not in source.models:
            raise HTTPException(
                status_code=400,
                detail=f"模型 {model_name} 不属于配置源 {source_name}",
            )
        if not source.api_key:
            raise HTTPException(
                status_code=400,
                detail=f"请先配置 {source_name} 的 API Key",
            )
        seen.add(key)
        if reasoning_effort == "none" and (
            source.name.lower() == "openrouter" or "openrouter.ai" in source.base_url.lower()
        ):
            reasoning_effort = "minimal"
        resolved.append({
            "key": key,
            "source_name": source_name,
            "model": model_name,
            "source": source,
            "reasoning_effort": reasoning_effort,
        })

    if not resolved:
        raise HTTPException(status_code=400, detail="请至少选择一个模型")
    return resolved


def public_model_targets(targets: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    return [
        {
            "key": target["key"],
            "source_name": target["source_name"],
            "model": target["model"],
            "reasoning_effort": target["reasoning_effort"],
        }
        for target in targets
    ]

# ==================== 会话管理全局状态 ====================
# 使用新的存储架构：按月分组存储，索引与内容分离
current_session_id: str = None  # 当前活动的会话 ID
current_session_cache: Session = None  # 当前会话缓存（避免频繁读取磁盘）


def init_default_session() -> Session:
    """
    初始化默认会话（首次启动或会话为空时调用）
    
    创建一个新的空会话，包含默认配置，并设置为当前活动会话
    
    Returns:
        Session: 新创建的会话对象
    """
    global current_session_id, current_session_cache
    
    session_id = generate_session_id()
    current_time = int(time.time())
    
    default_session = Session(
        id=session_id,
        title="新对话",
        created_at=current_time,
        updated_at=current_time,
        messages=[],
        session_config=create_default_session_config()
    )
    
    # 保存到磁盘（自动按月分组）
    session_storage.save_session(default_session)
    session_storage.set_current_session(session_id)
    
    # 更新全局状态
    current_session_id = session_id
    current_session_cache = default_session
    
    logger.info(f"创建默认会话: {session_id}")
    return default_session


def load_initial_state():
    """
    加载初始状态（服务启动时调用）
    
    从磁盘加载会话索引，恢复上次的会话状态
    如果没有会话，自动创建默认会话
    """
    global current_session_id
    
    # 加载轻量级索引（不包含消息内容）
    index_list = session_storage.load_index()
    
    if not index_list.sessions:
        logger.info("未找到已保存的会话，创建默认会话")
        init_default_session()
    else:
        # 恢复上次的当前会话
        current_session_id = index_list.current_session_id or index_list.sessions[0].id
        logger.info(f"加载会话索引: {len(index_list.sessions)} 个，当前会话: {current_session_id}")


def get_current_session() -> Session:
    """
    获取当前活动会话（带缓存机制）
    
    优先从内存缓存读取，缓存失效时从磁盘加载
    如果会话不存在，自动创建新会话
    
    Returns:
        Session: 当前会话对象
    """
    global current_session_cache
    
    # 缓存命中：直接返回
    if current_session_cache and current_session_cache.id == current_session_id:
        return current_session_cache
    
    # 缓存未命中：从磁盘加载
    session = session_storage.load_session(current_session_id)
    
    if not session:
        # 会话不存在（可能被外部删除），创建新会话
        logger.warning(f"当前会话 {current_session_id} 不存在，创建新会话")
        return init_default_session()
    
    # 更新缓存
    current_session_cache = session
    return session


def save_current_session():
    """
    保存当前会话到磁盘
    
    自动更新索引中的消息数量统计和更新时间
    """
    if current_session_cache:
        session_storage.save_session(current_session_cache)
        logger.debug(f"保存会话: {current_session_cache.id}")


def _screenshot_session_dir(session_id: str) -> Path:
    """Return the private screenshot directory for one validated session id."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", session_id):
        raise HTTPException(status_code=400, detail="无效的会话 ID")
    directory = SCREENSHOT_DIR / session_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _find_screenshot(session_id: str, attachment_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{24}", attachment_id):
        raise HTTPException(status_code=404, detail="截图不存在")
    directory = _screenshot_session_dir(session_id)
    matches = [path for path in directory.glob(f"{attachment_id}.*") if path.is_file()]
    if len(matches) != 1:
        raise HTTPException(status_code=404, detail="截图不存在")
    return matches[0]


def _delete_screenshot_files(
    session_id: str,
    attachment_ids: Optional[List[str]] = None,
) -> None:
    """Delete only screenshot files inside one validated session directory."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", session_id):
        return
    directory = SCREENSHOT_DIR / session_id
    if not directory.is_dir():
        return
    allowed_ids = set(attachment_ids) if attachment_ids is not None else None
    for path in directory.iterdir():
        if path.is_file() and (allowed_ids is None or path.stem in allowed_ids):
            path.unlink()
    try:
        directory.rmdir()
    except OSError:
        pass


def _unreferenced_attachment_ids(session: Session, attachment_ids: List[str]) -> List[str]:
    referenced = {
        attachment.id for message in session.messages for attachment in message.attachments
    }
    return [attachment_id for attachment_id in attachment_ids if attachment_id not in referenced]


def _detect_screenshot_mime(data: bytes) -> Optional[str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _load_message_attachments(
    session_id: str,
    attachment_ids: List[str],
) -> List[MessageAttachment]:
    attachments = []
    for attachment_id in attachment_ids:
        path = _find_screenshot(session_id, attachment_id)
        mime_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(path.suffix.lower())
        if not mime_type:
            raise HTTPException(status_code=400, detail="不支持的截图格式")
        attachments.append(MessageAttachment(
            id=attachment_id,
            mime_type=mime_type,
            filename=path.name,
            size=path.stat().st_size,
        ))
    return attachments


def _multimodal_user_content(
    session_id: str,
    text: str,
    attachments: List[MessageAttachment],
) -> Any:
    """Build OpenAI-compatible text and image content parts."""
    if not attachments:
        return text
    parts: List[Dict[str, Any]] = [{"type": "text", "text": text}]
    for attachment in attachments:
        path = _find_screenshot(session_id, attachment.id)
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{attachment.mime_type};base64,{encoded}",
            },
        })
    return parts


def attach_recording_to_session(session_id: Optional[str], audio_file: Optional[str]) -> None:
    """Persist the generated WAV filename on the session that started recording."""
    global current_session_cache

    if not session_id or not audio_file:
        return

    audio_path = Path(audio_file).resolve()
    try:
        audio_path.relative_to(VOICE_DIR.resolve())
    except ValueError:
        logger.warning(f"忽略 voices 目录之外的录音文件: {audio_path}")
        return

    session = (
        current_session_cache
        if current_session_cache and current_session_cache.id == session_id
        else session_storage.load_session(session_id)
    )
    if not session:
        logger.warning(f"录音对应的会话不存在: {session_id}")
        return

    if audio_path.name not in session.audio_files:
        session.audio_files.append(audio_path.name)
        session.updated_at = int(time.time())
        session_storage.save_session(session)
        if session_id == current_session_id:
            current_session_cache = session
        logger.info(f"录音已关联到会话: session={session_id}, file={audio_path.name}")


def get_conversation_history() -> List[ChatMessage]:
    """
    获取当前会话的消息历史（向后兼容接口）
    
    Returns:
        List[ChatMessage]: 消息列表
    """
    return get_current_session().messages


# 服务启动时加载初始状态
load_initial_state()

# 如果配置了 API Key，自动初始化客户端
if api_config.api_key:
    try:
        openai_client = OpenAI(
            api_key=api_config.api_key,
            base_url=api_config.base_url
        )
        logger.info(f"从 config.py 加载 OpenAI 配置成功: {current_config.current_source} - {current_config.current_model}")
    except Exception as e:
        logger.error(f"初始化 OpenAI 客户端失败: {e}")

# 预热流式识别实例（应用启动时）
try:
    streaming_asr_pool = StreamingASR(preload=True)
    logger.info("🔥 [预热成功] 流式识别实例已预热，首次录音将更快启动")
except Exception as e:
    logger.warning(f"⚠️ [预热失败] 流式识别预热失败: {e}")


async def preheat_next_instance():
    """预热下一个实例（后台任务）"""
    global streaming_asr_pool
    try:
        # 短暂延迟，避免影响当前请求
        await asyncio.sleep(0.5)
        
        if not streaming_asr_pool:  # 只有池为空时才预热
            streaming_asr_pool = StreamingASR(preload=True)
            logger.info("🔥 [预热完成] 下一个流式识别实例已预热")
    except Exception as e:
        logger.warning(f"⚠️ [预热失败] 后台预热失败: {e}")


# ==================== 配置管理 API ====================

@router.get("/config")
async def get_config():
    """
    获取所有 API 配置源和当前使用的配置
    
    Returns:
        ConfigList: 包含所有配置源、当前选中的源和模型，以及快捷键配置
    """
    logger.info("获取配置列表")
    # 确保返回最新的 config_sources
    current_config.sources = config_sources
    
    # 添加快捷键配置
    from config import HOTKEY_CONFIG
    result = current_config.dict()
    result['hotkey'] = HOTKEY_CONFIG
    
    return result


@router.post("/config/switch")
async def switch_config(source_name: str, model: str):
    """
    切换全局配置源和模型（会影响所有新会话）
    
    Args:
        source_name: 配置源名称（如 "OpenRouter", "OpenAI"）
        model: 模型名称（必须在该配置源的模型列表中）
    
    Returns:
        dict: 切换结果
    
    Raises:
        HTTPException: 配置源不存在或模型不在列表中
    """
    global openai_client, api_config, current_config
    
    # 1. 验证配置源是否存在
    source = next((s for s in config_sources if s.name == source_name), None)
    if not source:
        logger.error(f"配置源不存在: {source_name}")
        raise HTTPException(status_code=404, detail=f"配置源 {source_name} 不存在")
    
    # 2. 验证模型是否在该源的模型列表中
    if model not in source.models:
        logger.error(f"模型 {model} 不在配置源 {source_name} 的模型列表中")
        raise HTTPException(
            status_code=400, 
            detail=f"模型 {model} 不在配置源 {source_name} 的模型列表中"
        )
    
    # 3. 更新全局配置
    current_config.current_source = source_name
    current_config.current_model = model
    
    # 4. 更新向后兼容的配置对象
    api_config = ConfigModel(
        api_key=source.api_key,
        model=model,
        base_url=source.base_url
    )
    
    logger.info(f"切换全局配置: {source_name} - {model}")
    
    # 5. 重新初始化 OpenAI 客户端
    if api_config.api_key:
        try:
            openai_client = OpenAI(
                api_key=api_config.api_key,
                base_url=api_config.base_url
            )
            logger.info("OpenAI 客户端重新初始化成功")
        except Exception as e:
            logger.error(f"OpenAI 客户端初始化失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"客户端初始化失败: {str(e)}")
    else:
        logger.warning(f"配置源 {source_name} 没有 API Key")
    
    return {
        "success": True, 
        "message": f"已切换到 {source_name} - {model}"
    }


@router.post("/config/update")
async def update_config_source(source: ConfigSource):
    """更新某个配置源（如修改 API Key）"""
    global config_sources, current_config, api_config, openai_client
    
    # 查找并更新配置源
    for i, s in enumerate(config_sources):
        if s.name == source.name:
            config_sources[i] = source
            logger.info(f"更新配置源: {source.name}")
            
            # 如果是当前使用的配置源，更新 api_config 和客户端
            if current_config.current_source == source.name:
                api_config = ConfigModel(
                    api_key=source.api_key,
                    model=current_config.current_model,
                    base_url=source.base_url
                )
                
                if api_config.api_key:
                    try:
                        openai_client = OpenAI(
                            api_key=api_config.api_key,
                            base_url=api_config.base_url
                        )
                        logger.info("OpenAI 客户端重新初始化成功")
                    except Exception as e:
                        logger.error(f"OpenAI 客户端重新初始化失败: {e}", exc_info=True)
                        raise HTTPException(status_code=500, detail=str(e))
            
            # 保存到文件
            if not save_config_to_file():
                raise HTTPException(status_code=500, detail="保存配置到文件失败")
            
            return {"success": True, "message": f"配置源 {source.name} 已更新并保存"}
    
    raise HTTPException(status_code=404, detail=f"配置源 {source.name} 不存在")


@router.post("/config")
async def save_config(config: ConfigModel):
    """保存 API 配置（向后兼容接口）"""
    global openai_client, api_config
    
    api_config = config
    
    logger.info(f"保存配置: base_url={config.base_url}, model={config.model}")
    
    # 初始化 OpenAI 客户端
    if config.api_key:
        try:
            openai_client = OpenAI(
                api_key=config.api_key,
                base_url=config.base_url
            )
            logger.info("OpenAI 客户端初始化成功")
        except Exception as e:
            logger.error(f"OpenAI 客户端初始化失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    return {"success": True, "message": "配置已保存"}


@router.post("/config/add")
async def add_config_source(source: ConfigSource):
    """新增配置源"""
    global config_sources
    
    # 检查是否已存在同名配置源
    if any(s.name == source.name for s in config_sources):
        logger.error(f"配置源已存在: {source.name}")
        raise HTTPException(status_code=400, detail=f"配置源 {source.name} 已存在")
    
    # 添加配置源
    config_sources.append(source)
    # 同步更新 current_config.sources
    current_config.sources = config_sources
    logger.info(f"新增配置源: {source.name}")
    
    # 保存到文件
    if not save_config_to_file():
        raise HTTPException(status_code=500, detail="保存配置到文件失败")
    
    return {"success": True, "message": f"配置源 {source.name} 已新增并保存"}


@router.delete("/config/source/{source_name}")
async def delete_config_source(source_name: str):
    """删除配置源"""
    global config_sources, current_config
    
    # 至少保留一个配置源
    if len(config_sources) <= 1:
        logger.error("至少需要保留一个配置源")
        raise HTTPException(status_code=400, detail="至少需要保留一个配置源")
    
    # 不能删除当前正在使用的配置源
    if current_config.current_source == source_name:
        logger.error(f"不能删除当前正在使用的配置源: {source_name}")
        raise HTTPException(
            status_code=400, 
            detail=f"不能删除当前正在使用的配置源 {source_name}，请先切换到其他配置源"
        )
    
    # 查找并删除配置源
    original_length = len(config_sources)
    config_sources[:] = [s for s in config_sources if s.name != source_name]
    
    if len(config_sources) == original_length:
        logger.error(f"配置源不存在: {source_name}")
        raise HTTPException(status_code=404, detail=f"配置源 {source_name} 不存在")
    
    # 同步更新 current_config.sources
    current_config.sources = config_sources
    
    logger.info(f"删除配置源: {source_name}")
    
    # 保存到文件
    if not save_config_to_file():
        raise HTTPException(status_code=500, detail="保存配置到文件失败")
    
    return {"success": True, "message": f"配置源 {source_name} 已删除并保存"}


@router.get("/recording/devices")
def get_recording_devices():
    """列出实际执行录音的主机上的输入设备。"""
    import pyaudio

    audio = pyaudio.PyAudio()
    try:
        try:
            default_index = int(audio.get_default_input_device_info()['index'])
        except OSError:
            default_index = None
        devices = []
        for index in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(index)
            if info['maxInputChannels'] > 0:
                devices.append({'index': index, 'name': info['name']})
        return {'devices': devices, 'default_index': default_index}
    finally:
        audio.terminate()


@router.post("/recording/start")
async def start_recording(request: Optional[RecordingStartRequest] = None):
    """开始录音 - 实时流式模式（支持预热加速）"""
    global streaming_asr, streaming_asr_pool
    
    start_time = time.time()
    logger.info(f"🟢 [开始录音] 收到请求 - {time.strftime('%H:%M:%S', time.localtime(start_time))}.{int((start_time % 1) * 1000)}")
    
    # 使用临时变量，避免在失败时影响全局状态
    temp_asr = None
    
    try:
        # 如果已经有正在进行的录音，先清理
        if streaming_asr:
            logger.warning("⚠️ [清理旧实例] 检测到旧的录音实例，先清理...")
            previous_asr = streaming_asr
            try:
                await previous_asr.stop_streaming()
                attach_recording_to_session(
                    getattr(previous_asr, "session_id", None),
                    previous_asr.saved_audio_file,
                )
            except:
                pass
            streaming_asr = None
        
        # 使用预热的实例（如果可用）
        if streaming_asr_pool:
            logger.info("🔥 [使用预热实例] 使用预热的实例，加速启动...")
            temp_asr = streaming_asr_pool
            streaming_asr_pool = None  # 清空池
            
            # 异步预热下一个实例（不阻塞当前请求）
            asyncio.create_task(preheat_next_instance())
        else:
            # 创建新的实时流式识别实例
            logger.info("🔧 [创建实例] 创建新的 StreamingASR 实例...")
            temp_asr = StreamingASR()

        # Capture ownership now so later session switches cannot reassign audio.
        temp_asr.session_id = current_session_id
        temp_asr.input_device_index = request.input_device_index if request else None
        temp_asr.requested_device_name = request.input_device_name if request else None
        
        # 启动实时识别（作为后台任务）
        logger.info("🚀 [启动任务] 启动实时识别任务（录音将立即开始）...")
        task = asyncio.create_task(temp_asr.start_streaming())
        
        # 保存 task 引用到实例，以便检查状态
        temp_asr._task = task
        
        # 短暂等待确保录音已启动（只等待50ms，录音应该已经开始）
        logger.info("⏳ [等待录音] 等待录音启动...")
        await asyncio.sleep(0.05)  # 50ms足够启动录音线程
        
        # 检查任务是否立即失败
        if task.done() and task.exception():
            error = task.exception()
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"❌ [启动失败] 任务失败 (耗时: {elapsed:.2f}ms): {error}")
            raise Exception(f"启动任务失败: {error}")
        
        # 录音已经开始，连接将在后台建立 - 只有成功后才设置全局变量
        streaming_asr = temp_asr
        
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"✅ [录音已启动] 总耗时: {elapsed:.2f}ms")
        logger.info(f"🎤 [状态] 录音已开始，音频正在缓冲，WebSocket 连接将在后台建立")
        logger.info(f"💡 [优化] 前端响应延迟: ~{elapsed:.0f}ms（相比之前的700ms+大幅提升）")
        
        return RecordingResponse(success=True, message="开始实时录音识别")
        
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        logger.error(f"❌ [录音失败] 启动录音失败 (耗时: {elapsed:.2f}ms): {e}", exc_info=True)
        
        # 清理失败的临时实例（不影响全局状态）
        if temp_asr:
            try:
                await temp_asr.stop_streaming()
                attach_recording_to_session(
                    getattr(temp_asr, "session_id", None),
                    temp_asr.saved_audio_file,
                )
            except:
                pass
        # 注意：这里不设置 streaming_asr = None，保持原有状态
        
        return RecordingResponse(success=False, message=str(e))


@router.get("/recording/status")
async def get_recording_status():
    """获取录音状态"""
    global streaming_asr
    
    if not streaming_asr:
        return {
            "is_recording": False,
            "auto_stopped": False,
            "partial_text": "",
        }
    
    return {
        "is_recording": streaming_asr.is_recording,
        "auto_stopped": streaming_asr.auto_stopped,
        # Soniox emits hypotheses while audio is still being sent. Expose
        # the latest one so the UI can render the live transcript.
        "partial_text": (
            streaming_asr.partial_text
            or streaming_asr.result_text
            or ""
        ),
    }


@router.post("/recording/stop")
async def stop_recording():
    """停止录音并获取识别结果 - 实时流式模式"""
    global streaming_asr
    
    request_start_time = time.time()
    logger.info(f"🔴 [停止录音] 收到请求 - {time.strftime('%H:%M:%S', time.localtime(request_start_time))}.{int((request_start_time % 1) * 1000)}")
    
    try:
        if not streaming_asr:
            logger.warning("⚠️ [无录音] 没有正在进行的录音")
            logger.warning("⚠️ [状态检查] streaming_asr 为 None，可能是启动失败或已经停止")
            return RecordingResponse(success=False, message="没有正在进行的录音，请先点击开始录音")
        
        # 保存实例引用，防止并发请求导致的问题
        current_asr = streaming_asr
        # 立即清空全局变量，防止重复调用
        streaming_asr = None
        
        # 停止流式识别并获取结果
        logger.info("🛑 [停止识别] 调用 stop_streaming()...")
        stop_start = time.time()
        
        text, error_msg = await current_asr.stop_streaming()
        attach_recording_to_session(
            getattr(current_asr, "session_id", None),
            current_asr.saved_audio_file,
        )
        
        stop_elapsed = (time.time() - stop_start) * 1000
        total_elapsed = (time.time() - request_start_time) * 1000
        
        if text:
            logger.info(f"✅ [识别成功] 文本: \"{text}\" (停止耗时: {stop_elapsed:.2f}ms, 总耗时: {total_elapsed:.2f}ms)")
            logger.info(f"📈 [耗时统计] 停止识别: {stop_elapsed:.2f}ms | 总计: {total_elapsed:.2f}ms")
            return RecordingResponse(success=True, text=text)
        else:
            detailed_message = error_msg or "识别失败，请确保说话清晰且时长足够"
            logger.warning(f"❌ [识别失败] {detailed_message} (总耗时: {total_elapsed:.2f}ms)")
            return RecordingResponse(success=False, message=detailed_message)
            
    except Exception as e:
        total_elapsed = (time.time() - request_start_time) * 1000
        logger.error(f"❌ [录音处理异常] 耗时: {total_elapsed:.2f}ms - {e}", exc_info=True)
        # 注意：streaming_asr 已经在 try 块开始时清空了
        return RecordingResponse(success=False, message=f"录音处理异常: {str(e)}")


@router.post("/attachments/screenshots")
async def upload_screenshot(
    session_id: str = Form(...),
    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None),
    screenshot: UploadFile = File(...),
):
    """Validate and store a browser-tab screenshot for a chat message."""
    if not session_storage.load_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    data = await screenshot.read(MAX_SCREENSHOT_BYTES + 1)
    await screenshot.close()
    if not data:
        raise HTTPException(status_code=400, detail="截图内容为空")
    if len(data) > MAX_SCREENSHOT_BYTES:
        raise HTTPException(status_code=413, detail="截图不能超过 8MB")

    detected_mime = _detect_screenshot_mime(data)
    if detected_mime not in SCREENSHOT_MIME_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 PNG、JPEG 或 WebP 截图")

    attachment_id = uuid.uuid4().hex[:24]
    filename = attachment_id + SCREENSHOT_MIME_EXTENSIONS[detected_mime]
    path = _screenshot_session_dir(session_id) / filename
    path.write_bytes(data)

    attachment = MessageAttachment(
        id=attachment_id,
        mime_type=detected_mime,
        filename=filename,
        width=width if width and width > 0 else None,
        height=height if height and height > 0 else None,
        size=len(data),
    )
    return attachment.dict()


@router.get("/attachments/{session_id}/{attachment_id}")
async def get_screenshot(session_id: str, attachment_id: str):
    """Serve a screenshot that belongs to a local chat session."""
    if not session_storage.load_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    path = _find_screenshot(session_id, attachment_id)
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type)


@router.delete("/attachments/{session_id}/{attachment_id}")
async def delete_unused_screenshot(session_id: str, attachment_id: str):
    """Discard an uploaded image that was never attached to a saved message."""
    session = session_storage.load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if any(
        attachment.id == attachment_id
        for message in session.messages for attachment in message.attachments
    ):
        raise HTTPException(status_code=409, detail="图片已被消息使用")
    path = _find_screenshot(session_id, attachment_id)
    path.unlink()
    return {"success": True}


@router.post("/chat")
async def chat(request: ChatRequest):
    """发送消息（流式返回）- 支持树形对话和并行响应"""
    if not request.message:
        raise HTTPException(status_code=400, detail="消息不能为空")
    
    logger.info(f"收到聊天请求: {request.message[:50]}...")
    
    # Explicit session ownership prevents a tab capture from landing in a
    # different session if the user switches conversations while uploading.
    if request.session_id:
        current_session = session_storage.load_session(request.session_id)
        if not current_session:
            raise HTTPException(status_code=404, detail="会话不存在")
    else:
        current_session = get_current_session()
    chat_epoch = generation_epochs.get(current_session.id)
    session_config = current_session.session_config
    message_attachments = _load_message_attachments(
        current_session.id, request.attachment_ids
    )
    
    model_targets = resolve_model_targets(session_config)
    models_to_use = [target["model"] for target in model_targets]
    
    # 生成用户消息 ID
    user_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    current_time = int(time.time())
    
    # 创建用户消息（树形结构）
    user_message = ChatMessage(
        id=user_msg_id,
        parent_id=request.parent_id,  # 从请求中获取父消息 ID
        role="user",
        content=request.message,
        type="image" if message_attachments else "text",
        attachments=message_attachments,
        created_at=current_time,
        children_ids=[]
    )
    
    # 如果有父消息，更新父消息的 children_ids
    if request.parent_id:
        for msg in current_session.messages:
            if msg.id == request.parent_id:
                if user_msg_id not in msg.children_ids:
                    msg.children_ids.append(user_msg_id)
                break
    
    # 添加用户消息到当前会话
    current_session.messages.append(user_message)
    current_session.updated_at = current_time
    
    # 如果是第一条消息，自动生成标题（取前20个字符）
    if len(current_session.messages) == 1 and current_session.title == "新对话":
        current_session.title = request.message[:20] + ("..." if len(request.message) > 20 else "")

    # Persist the question before streaming so another screenshot can start
    # immediately and see it. There is no await between load/save below.
    if not session_storage.save_session(current_session):
        raise HTTPException(status_code=500, detail="保存问题失败")

    def save_chat_answer(assistant_msg: ChatMessage) -> None:
        """Merge this answer into the latest session instead of a stale snapshot."""
        if generation_epochs.get(current_session.id) != chat_epoch:
            raise asyncio.CancelledError()
        latest_session = session_storage.load_session(current_session.id)
        if not latest_session:
            raise RuntimeError("会话已被删除，无法保存回答")
        for index, message in enumerate(latest_session.messages):
            if message.id == user_msg_id:
                if assistant_msg.id not in message.children_ids:
                    message.children_ids.append(assistant_msg.id)
                latest_session.messages.insert(index + 1, assistant_msg)
                latest_session.updated_at = int(time.time())
                if not session_storage.save_session(latest_session):
                    raise RuntimeError("保存回答失败")
                return
        raise RuntimeError("找不到本次问题，无法保存回答")

    context_settings = resolve_chat_context_config(session_config)
    
    def build_messages_for_model(
        target_model: str,
        target_source_name: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        为特定模型构建消息历史
        
        Args:
            target_model: 目标模型名称
            
        Returns:
            List[Dict[str, str]]: OpenAI 格式的消息列表
        """
        api_messages = []
        
        # 1. 添加 system prompt（如果有）
        system_prompt = compose_session_system_prompt(current_session)
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        
        # 2. 只取最近 N 轮用户问题，排除最后一条（当前用户消息）。
        # 一轮按 user 消息计数，而不是按底层 message 条数计数。
        history_messages = current_session.messages[:-1]
        user_indexes = [
            index for index, msg in enumerate(history_messages)
            if msg.role == "user"
        ]
        max_history_turns = context_settings["max_history_turns"]
        if user_indexes and len(user_indexes) > max_history_turns:
            history_messages = history_messages[user_indexes[-max_history_turns]:]

        include_assistant = context_settings["include_assistant_history"]
        for msg in history_messages:
            if msg.role == 'user':
                # 默认只发送用户问题，节省上下文；assistant 历史可配置打开。
                api_messages.append({"role": "user", "content": msg.content})
            elif msg.role == 'assistant' and include_assistant:
                # assistant 消息：只添加当前模型的回复
                assistant_content = None
                
                # 检查是否是并行响应
                if msg.is_parallel_response and msg.parallel_models:
                    # 并行响应：从 parallel_models 中找到当前模型的回复
                    for model_data in msg.parallel_models:
                        model_info = model_data.get('model_info', {})
                        same_model = (
                            model_data.get('model') == target_model
                            or model_info.get('name') == target_model
                        )
                        same_source = (
                            not target_source_name
                            or not model_info.get('provider')
                            or model_info.get('provider') == target_source_name
                        )
                        if same_model and same_source:
                            assistant_content = model_data.get('content', '')
                            break
                else:
                    # 单模型响应：检查是否是当前模型
                    if (
                        msg.model_info
                        and msg.model_info.name == target_model
                        and (
                            not target_source_name
                            or not msg.model_info.provider
                            or msg.model_info.provider == target_source_name
                        )
                    ):
                        assistant_content = msg.content
                    elif not msg.model_info:
                        # 如果没有 model_info，说明是旧数据，直接使用
                        assistant_content = msg.content
                
                # 添加 assistant 消息（如果找到了对应模型的回复）
                if assistant_content is not None:
                    api_messages.append({"role": "assistant", "content": assistant_content})

        api_messages = trim_history_context(
            api_messages, context_settings["max_history_chars"], target_model
        )
        
        rendered_user_prompt = render_session_user_prompt(
            current_session, user_message.content
        )
        scoped_messages = build_scoped_request(
            api_messages, rendered_user_prompt, include_assistant
        )
        if message_attachments:
            scoped_messages[-1]["content"] = _multimodal_user_content(
                current_session.id,
                scoped_messages[-1]["content"],
                message_attachments,
            )
        return scoped_messages
    
    async def generate():
        tasks = []
        import asyncio
        try:
            logger.info(f"📝 会话总消息数: {len(current_session.messages)}")
            is_parallel = len(models_to_use) > 1
            logger.info(f"🚀 开始流式调用: models={models_to_use}, parallel={is_parallel}, session={current_session.id}")
            
            # 准备配置信息用于日志记录
            config_info = {
                "temperature": session_config.temperature if session_config else 0.7,
                "top_p": session_config.top_p if session_config else 1.0
            }
            
            if is_parallel:
                # 多模型并行调用模式（真正的并行流式输出）
                yield f"data: {json.dumps({'type': 'multi_model_start', 'models': models_to_use, 'targets': public_model_targets(model_targets)}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)
                
                assistant_messages = []  # 存储所有模型的响应
                model_results = {}  # 存储每个模型的完整响应
                model_messages_map = {}  # 存储每个模型的消息历史（用于日志记录）
                
                # 为每个模型发送开始标记
                for model_index, target in enumerate(model_targets):
                    model_name = target['model']
                    yield f"data: {json.dumps({'type': 'model_start', 'model_index': model_index, 'model': model_name, 'model_key': target['key'], 'source_name': target['source_name']}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0)
                    model_results[model_index] = {
                        'content': '',
                        'start_time': time.time(),
                        'model': model_name,
                        'model_key': target['key'],
                        'source_name': target['source_name'],
                        'reasoning_effort': target['reasoning_effort'],
                    }
                
                logger.info(f"🚀 并行调用 {len(models_to_use)} 个模型")
                
                # 创建队列接收来自所有模型的 chunks
                chunk_queue = asyncio.Queue()
                
                # 定义单个模型的流式处理任务
                async def stream_model(model_index: int, target: Dict[str, Any]):
                    model_name = target['model']
                    source = target['source']
                    try:
                        # 为当前模型构建专属的消息历史
                        model_messages = build_messages_for_model(
                            model_name, target['source_name']
                        )
                        logger.info(f"🔧 模型 {target['key']} 的消息历史: {len(model_messages)} 条")
                        log_model_request_context(
                            target['key'], model_messages, context_settings=context_settings
                        )
                        
                        # 保存消息历史用于日志记录
                        model_messages_map[target['key']] = model_messages
                        
                        # 创建异步客户端
                        client = AsyncOpenAI(
                            api_key=source.api_key,
                            base_url=source.base_url
                        )
                        
                        # 异步调用模型（流式）
                        request_params = dict(
                            model=model_name,
                            messages=model_messages,
                            temperature=session_config.temperature if session_config else 0.7,
                            top_p=session_config.top_p if session_config else 1.0,
                            stream=True,
                            **get_chat_completion_extra_params(
                                source, model_name, target['reasoning_effort']
                            )
                        )
                        request_preview = log_provider_request(source, request_params)
                        await chunk_queue.put({
                            "type": "provider_request",
                            "stage": "chat",
                            "model_key": target["key"],
                            "request": request_preview,
                        })
                        stream = await client.chat.completions.create(**request_params)
                        
                        chunk_count = 0
                        async for chunk in stream:
                            if not chunk.choices:
                                continue
                            content = chunk.choices[0].delta.content
                            if content:
                                model_results[model_index]['content'] += content
                                chunk_count += 1
                                
                                # 将 chunk 放入队列
                                await chunk_queue.put({
                                    'type': 'content',
                                    'model_index': model_index,
                                    'model': model_name,
                                    'model_key': target['key'],
                                    'source_name': target['source_name'],
                                    'data': content
                                })
                        
                        latency_ms = int((time.time() - model_results[model_index]['start_time']) * 1000)
                        logger.info(f"✅ 模型 {model_name} 完成: {len(model_results[model_index]['content'])} 字符, {chunk_count} chunks, 耗时 {latency_ms}ms")
                        
                        # 发送完成标记
                        await chunk_queue.put({
                            'type': 'model_done',
                            'model_index': model_index,
                            'model': model_name,
                            'model_key': target['key'],
                            'source_name': target['source_name'],
                            'latency_ms': latency_ms
                        })
                        
                    except Exception as e:
                        logger.error(f"❌ 模型 {model_name} 调用失败: {e}")
                        await chunk_queue.put({
                            'type': 'model_error',
                            'model_index': model_index,
                            'model': model_name,
                            'model_key': target['key'],
                            'source_name': target['source_name'],
                            'message': str(e)
                        })
                
                # 启动所有模型的并行任务
                tasks = []
                for model_index, target in enumerate(model_targets):
                    task = asyncio.create_task(stream_model(model_index, target))
                    tasks.append(task)
                
                # 从队列中读取并发送 chunks
                completed_models = 0
                while completed_models < len(models_to_use):
                    try:
                        # 等待队列中的下一个 chunk（超时 60 秒）
                        chunk_data = await asyncio.wait_for(chunk_queue.get(), timeout=60.0)
                        
                        # 发送到客户端
                        yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
                        await asyncio.sleep(0)
                        
                        # 检查是否有模型完成或出错
                        if chunk_data['type'] in ['model_done', 'model_error']:
                            completed_models += 1
                            
                    except asyncio.TimeoutError:
                        logger.error("⏱️ 等待模型响应超时")
                        break
                
                # 等待所有任务完成
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # 收集结果
                for model_index, result in model_results.items():
                    if result['content']:
                        assistant_messages.append({
                            'model': result['model'],
                            'model_key': result['model_key'],
                            'source_name': result['source_name'],
                            'reasoning_effort': result['reasoning_effort'],
                            'content': result['content'],
                            'latency_ms': int((time.time() - result['start_time']) * 1000)
                        })
                
                logger.info(f"🎉 所有模型并行完成，共 {len(assistant_messages)} 个")
                
                # 保存多模型响应 - 使用一个容器消息
                assistant_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
                assistant_msg_time = int(time.time())
                
                # 构建并行模型数据列表
                parallel_models_data = []
                for model_data in assistant_messages:
                    parallel_models_data.append({
                        "model": model_data['model'],
                        "model_key": model_data['model_key'],
                        "source_name": model_data['source_name'],
                        "content": model_data['content'],
                        "latency_ms": model_data['latency_ms'],
                        "model_info": {
                            "id": model_data['model_key'],
                            "name": model_data['model'],
                            "provider": model_data['source_name'],
                            "reasoning_effort": model_data['reasoning_effort'],
                        }
                    })
                
                # 创建一个多模型容器消息
                assistant_msg = ChatMessage(
                    id=assistant_msg_id,
                    parent_id=user_msg_id,
                    role="assistant",
                    scene_name=session_config.active_scene.name if session_config and session_config.active_scene else None,
                    content="",  # 容器消息内容为空
                    type="multi_model",  # 标记为多模型类型
                    created_at=assistant_msg_time,
                    children_ids=[],
                    is_parallel_response=True,
                    parallel_models=parallel_models_data  # 保存所有模型的响应
                )
                
                save_chat_answer(assistant_msg)
                
                # 记录每个模型的交互
                for idx, model_data in enumerate(parallel_models_data):
                    model_name = model_data['model_info']['name']
                    # 使用保存的消息历史（调用 API 时的消息）
                    model_messages = model_messages_map.get(model_data['model_key'], [])
                    log_model_interaction(
                        session_id=current_session.id,
                        model=model_data['model_key'],
                        messages=model_messages,
                        response=model_data['content'],
                        elapsed_time=model_data['latency_ms'] / 1000.0,
                        config=config_info
                    )
                
                logger.info(f"💾 多模型回复完成并保存，共 {len(assistant_messages)} 个模型")
                
                # 发送完成信号
                yield f"data: {json.dumps({'type': 'done', 'model_count': len(assistant_messages)}, ensure_ascii=False)}\n\n"
                
            else:
                # 单模型模式
                target = model_targets[0]
                model_to_use = target['model']
                source_to_use = target['source']
                start_time = time.time()
                
                # 为当前模型构建专属的消息历史
                model_messages = build_messages_for_model(
                    model_to_use, target['source_name']
                )
                logger.info(f"🔧 模型 {model_to_use} 的消息历史: {len(model_messages)} 条")
                log_model_request_context(
                    model_to_use, model_messages, context_settings=context_settings
                )
                
                client = OpenAI(
                    api_key=source_to_use.api_key,
                    base_url=source_to_use.base_url
                )
                
                # 调用 OpenAI API（流式）
                request_params = dict(
                    model=model_to_use,
                    messages=model_messages,
                    temperature=session_config.temperature if session_config else 0.7,
                    top_p=session_config.top_p if session_config else 1.0,
                    stream=True,
                    **get_chat_completion_extra_params(
                        source_to_use, model_to_use, target['reasoning_effort']
                    )
                )
                request_preview = log_provider_request(source_to_use, request_params)
                yield f"data: {json.dumps({'type': 'provider_request', 'stage': 'chat', 'model_key': target['key'], 'request': request_preview}, ensure_ascii=False)}\n\n"
                stream = await asyncio.to_thread(client.chat.completions.create, **request_params)
                
                assistant_message = ''
                chunk_count = 0
                last_log_time = time.time()
                
                async for chunk in iterate_provider_stream(stream):
                    if not chunk.choices:
                        continue
                    content = chunk.choices[0].delta.content
                    if content:
                        assistant_message += content
                        chunk_count += 1
                        
                        # 立即发送这个 chunk
                        chunk_data = f"data: {json.dumps({'type': 'content', 'data': content}, ensure_ascii=False)}\n\n"
                        yield chunk_data
                        
                        # 强制让出控制权，确保立即发送
                        await asyncio.sleep(0)
                        
                        # 每 10 个 chunk 或每 2 秒记录一次日志
                        current_time_check = time.time()
                        if chunk_count % 10 == 0 or (current_time_check - last_log_time) >= 2:
                            logger.info(f"📤 已发送 {chunk_count} 个chunks, 当前长度: {len(assistant_message)}")
                            last_log_time = current_time_check
                
                # 单模型模式保存
                latency_ms = int((time.time() - start_time) * 1000)
                logger.info(f"✅ 流式发送完成: {chunk_count} 个chunks")
                
                # 记录模型交互
                log_model_interaction(
                    session_id=current_session.id,
                    model=model_to_use,
                    messages=model_messages,
                    response=assistant_message,
                    elapsed_time=latency_ms / 1000.0,
                    config=config_info
                )
                
                # 生成 assistant 消息 ID
                assistant_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
                assistant_msg_time = int(time.time())
                
                # 创建 assistant 消息（包含完整元数据）
                assistant_msg = ChatMessage(
                    id=assistant_msg_id,
                    parent_id=user_msg_id,
                    role="assistant",
                    scene_name=session_config.active_scene.name if session_config and session_config.active_scene else None,
                    content=assistant_message,
                    type="text",
                    created_at=assistant_msg_time,
                    children_ids=[],
                    model_info={
                        "id": target['key'],
                        "name": model_to_use,
                        "provider": source_to_use.name if source_to_use else "unknown",
                        "reasoning_effort": target['reasoning_effort'],
                    },
                    usage={
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0
                    },
                    status="success",
                    latency_ms=latency_ms
                )
                
                # 更新用户消息的 children_ids
                save_chat_answer(assistant_msg)
                
                logger.info(f"💾 AI 回复完成并保存，总长度: {len(assistant_message)}, session={current_session.id}")
                
                # 发送完成信号（包含消息 ID）
                done_data = {'type': 'done', 'message_id': assistant_msg_id}
                yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"❌ AI 调用出错: {e}", exc_info=True)
            # 记录错误
            if 'models_to_use' in locals() and 'api_messages' in locals():
                for model in [target['key'] for target in model_targets]:
                    log_error(
                        session_id=current_session.id,
                        model=model,
                        messages=api_messages,
                        error=e,
                        stage="streaming"
                    )
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    
    return StreamingResponse(
        generate(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 Nginx 缓冲
        }
    )


def build_message_path(session: Session, target_msg_id: str) -> List[ChatMessage]:
    """
    构建从根节点到目标消息的对话路径
    
    Args:
        session: 会话对象
        target_msg_id: 目标消息 ID
    
    Returns:
        List[ChatMessage]: 消息路径（按时间顺序）
    """
    # 创建消息字典方便查找
    msg_dict = {msg.id: msg for msg in session.messages}
    
    # 从目标消息回溯到根节点
    path = []
    current_id = target_msg_id
    
    while current_id:
        if current_id not in msg_dict:
            break
        
        msg = msg_dict[current_id]
        path.insert(0, msg)  # 插入到开头
        current_id = msg.parent_id
    
    # 过滤掉 system 消息（它们在构建 API 请求时单独处理）
    path = [msg for msg in path if msg.role != "system"]
    
    return path


@router.post("/chat/clear")
async def clear_chat():
    """清空当前会话的对话历史"""
    current_session = get_current_session()
    
    logger.info(f"清空会话 {current_session_id} 的对话历史")
    _delete_screenshot_files(current_session.id)
    current_session.messages = []
    current_session.updated_at = int(time.time())
    
    # 保存到存储
    save_current_session()
    
    return {"success": True, "message": "对话已清空"}


@router.get("/chat/history")
async def get_history():
    """获取当前会话的对话历史"""
    return {"history": [msg.dict() for msg in get_conversation_history()]}


# ==================== 会话管理 API ====================

@router.get("/sessions")
async def get_sessions():
    """
    获取所有会话列表（仅索引，快速加载导航栏）
    
    返回轻量级索引，不包含消息内容，只包含：
    - 会话 ID、标题、创建/更新时间
    - 消息数量统计
    - 存储路径
    
    优化效果：即使有100个会话，响应时间也在 10-30ms
    
    Returns:
        SessionIndexList: 会话索引列表，按更新时间倒序排列
    """
    logger.info("获取会话列表")
    
    # 加载轻量级索引（不包含消息内容）
    index_list = session_storage.load_index()
    
    # 按 updated_at 降序排序（最新的在最上面）
    sorted_sessions = sorted(
        index_list.sessions, 
        key=lambda s: s.updated_at, 
        reverse=True
    )
    
    logger.debug(f"返回 {len(sorted_sessions)} 个会话索引")
    
    return SessionIndexList(
        sessions=sorted_sessions,
        current_session_id=current_session_id
    ).dict()


@router.post("/sessions")
async def create_session(title: str = "新对话"):
    """
    创建新会话并设置为当前活动会话
    
    Args:
        title: 会话标题（默认"新对话"）
    
    Returns:
        dict: 包含新创建的会话详情
        
    说明：
        - 会话自动按创建时间分月存储（如 data/storage/2026/01/）
        - 自动添加到会话索引中
        - 设置为当前活动会话
    """
    global current_session_id, current_session_cache
    
    try:
        session_id = generate_session_id()
        current_time = int(time.time())
        
        # 创建新会话对象
        new_session = Session(
            id=session_id,
            title=title,
            created_at=current_time,
            updated_at=current_time,
            messages=[],
            session_config=create_default_session_config()
        )
        
        # 保存到磁盘（自动按月分组）
        if not session_storage.save_session(new_session):
            logger.error(f"保存会话失败: {session_id}")
            raise HTTPException(status_code=500, detail="保存会话失败")
        
        # 设置为当前会话
        if not session_storage.set_current_session(session_id):
            logger.error(f"设置当前会话失败: {session_id}")
            raise HTTPException(status_code=500, detail="设置当前会话失败")
        
        current_session_id = session_id
        current_session_cache = new_session
        
        logger.info(f"创建新会话: {session_id} - {title}")
        
        return {
            "success": True,
            "message": "会话创建成功",
            "session": new_session.dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建会话异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """
    获取指定会话的完整详情（按需加载）
    
    包含完整的消息列表和会话配置
    只有当用户点击会话时才调用此API
    
    Args:
        session_id: 会话 ID
    
    Returns:
        Session: 完整的会话对象（包含所有消息）
    
    Raises:
        HTTPException: 会话不存在时返回 404
    """
    logger.info(f"获取会话详情: {session_id}")
    
    # 从磁盘加载完整会话内容
    session = session_storage.load_session(session_id)
    
    if not session:
        logger.warning(f"会话不存在: {session_id}")
        raise HTTPException(status_code=404, detail="会话不存在")
    
    logger.debug(f"返回会话: {session.title}, {len(session.messages)} 条消息")
    return session.dict()


@router.get("/sessions/{session_id}/audio/merged")
async def merge_session_audio(session_id: str):
    """Concatenate all WAV recordings associated with a session, in order."""
    session = session_storage.load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if not session.audio_files:
        raise HTTPException(status_code=404, detail="该会话没有已关联的录音")

    output = io.BytesIO()
    expected_params = None
    frames = []

    for filename in session.audio_files:
        audio_path = (VOICE_DIR / Path(filename).name).resolve()
        try:
            audio_path.relative_to(VOICE_DIR.resolve())
        except ValueError:
            logger.warning(f"跳过不安全的录音路径: {filename}")
            continue
        if not audio_path.is_file():
            logger.warning(f"跳过不存在的录音文件: {audio_path}")
            continue

        try:
            with wave.open(str(audio_path), "rb") as wav_file:
                params = (
                    wav_file.getnchannels(),
                    wav_file.getsampwidth(),
                    wav_file.getframerate(),
                    wav_file.getcomptype(),
                )
                if expected_params is None:
                    expected_params = params
                elif params != expected_params:
                    raise HTTPException(
                        status_code=409,
                        detail=f"录音格式不一致，无法合并: {filename}",
                    )
                frames.append(wav_file.readframes(wav_file.getnframes()))
        except HTTPException:
            raise
        except (wave.Error, OSError) as error:
            logger.warning(f"跳过无法读取的录音文件 {audio_path}: {error}")

    if expected_params is None or not frames:
        raise HTTPException(status_code=404, detail="该会话关联的录音文件已不存在或无法读取")

    channels, sample_width, frame_rate, compression = expected_params
    with wave.open(output, "wb") as merged:
        merged.setnchannels(channels)
        merged.setsampwidth(sample_width)
        merged.setframerate(frame_rate)
        merged.setcomptype(compression, "not compressed")
        for audio_frames in frames:
            merged.writeframes(audio_frames)

    output.seek(0)
    download_name = f"session-{session_id}-audio.wav"
    return StreamingResponse(
        output,
        media_type="audio/wav",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@router.post("/sessions/{session_id}/switch")
async def switch_session(session_id: str):
    """
    切换到指定会话（设置为当前活动会话）
    
    Args:
        session_id: 要切换到的会话 ID
    
    Returns:
        dict: 包含会话详情
    
    Raises:
        HTTPException: 会话不存在时返回 404
    
    说明：
        - 更新会话的 updated_at 时间戳
        - 更新全局当前会话 ID
        - 刷新会话缓存
    """
    global current_session_id, current_session_cache
    
    logger.info(f"切换会话: {session_id}")
    
    # 从磁盘加载会话
    session = session_storage.load_session(session_id)
    
    if not session:
        logger.warning(f"会话不存在: {session_id}")
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 更新全局状态
    current_session_id = session_id
    current_session_cache = session
    
    # 更新访问时间
    session.updated_at = int(time.time())
    session_storage.save_session(session)
    
    # 设置为当前会话
    session_storage.set_current_session(session_id)
    
    logger.info(f"切换成功: {session.title}")
    
    return {
        "success": True,
        "message": "会话切换成功",
        "session": session.dict()
    }


@router.put("/sessions/{session_id}/title")
async def update_session_title(session_id: str, title: str):
    """
    更新会话标题
    
    Args:
        session_id: 会话 ID
        title: 新标题
    
    Returns:
        dict: 更新后的会话详情
    
    Raises:
        HTTPException: 会话不存在时返回 404
    
    说明：
        - 同时更新会话文件和索引中的标题
        - 更新 updated_at 时间戳
    """
    logger.info(f"更新会话标题: {session_id} -> {title}")
    
    # 从磁盘加载会话
    session = session_storage.load_session(session_id)
    
    if not session:
        logger.warning(f"会话不存在: {session_id}")
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 更新标题和时间戳
    session.title = title
    session.updated_at = int(time.time())
    
    # 保存（自动更新索引）
    session_storage.save_session(session)
    
    # 如果是当前会话，更新缓存
    global current_session_cache
    if session_id == current_session_id and current_session_cache:
        current_session_cache = session
    
    logger.info(f"标题更新成功: {session_id}")
    
    return {
        "success": True,
        "message": "标题更新成功",
        "session": session.dict()
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    删除指定会话（包括所有消息和配置）
    
    Args:
        session_id: 要删除的会话 ID
    
    Returns:
        dict: 删除结果和新的当前会话 ID
    
    Raises:
        HTTPException:
            - 404: 会话不存在
            - 400: 尝试删除最后一个会话
    
    说明：
        - 物理删除磁盘上的会话文件
        - 从索引中移除
        - 如果删除的是当前会话，自动切换到其他会话
        - 至少保留一个会话（不允许删除最后一个）
    """
    global current_session_id, current_session_cache
    
    logger.info(f"删除会话: {session_id}")
    
    # 1. 检查会话是否存在
    index_list = session_storage.load_index()
    if not any(s.id == session_id for s in index_list.sessions):
        logger.warning(f"会话不存在: {session_id}")
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 2. 不允许删除最后一个会话
    if len(index_list.sessions) == 1:
        logger.warning("尝试删除最后一个会话")
        raise HTTPException(status_code=400, detail="至少需要保留一个会话")
    
    # 3. 如果删除的是当前会话，切换到其他会话
    if session_id == current_session_id:
        for s in index_list.sessions:
            if s.id != session_id:
                current_session_id = s.id
                current_session_cache = None  # 清除缓存，强制重新加载
                session_storage.set_current_session(current_session_id)
                logger.info(f"切换到新会话: {current_session_id}")
                break
    
    # 4. 执行删除操作（删除文件和索引）
    if session_storage.delete_session(session_id):
        _delete_screenshot_files(session_id)
        logger.info(f"会话删除成功: {session_id}")
    else:
        logger.error(f"会话删除失败: {session_id}")
        raise HTTPException(status_code=500, detail="删除会话失败")
    
    return {
        "success": True,
        "message": "会话删除成功",
        "current_session_id": current_session_id
    }


# ==================== 消息管理 API ====================

@router.put("/sessions/{session_id}/messages/{message_id}")
async def update_message(session_id: str, message_id: str, request: MessageUpdateRequest):
    """
    更新指定会话的指定消息
    
    Args:
        session_id: 会话 ID
        message_id: 消息 ID
        request: 消息更新请求（包含新内容）
    
    Returns:
        dict: 更新结果
    """
    session = session_storage.load_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # Validate every new image before changing the persisted message.
    replacement_attachments = (
        _load_message_attachments(session_id, request.attachment_ids)
        if request.attachment_ids is not None else None
    )
    removed_attachment_ids = []

    # 查找消息
    message_found = False
    for msg in session.messages:
        if msg.id == message_id:
            if replacement_attachments is not None:
                if msg.role != "user":
                    raise HTTPException(status_code=400, detail="只能编辑用户消息的图片")
                new_ids = {attachment.id for attachment in replacement_attachments}
                removed_attachment_ids = [attachment.id for attachment in msg.attachments if attachment.id not in new_ids]
                existing = {attachment.id: attachment for attachment in msg.attachments}
                msg.attachments = [existing.get(attachment.id, attachment) for attachment in replacement_attachments]
                msg.type = "image" if replacement_attachments else "text"
            msg.content = request.content
            msg.created_at = int(time.time())  # 更新时间戳
            message_found = True
            break
    
    if not message_found:
        raise HTTPException(status_code=404, detail="消息不存在")
    
    session.updated_at = int(time.time())
    session_storage.save_session(session)
    if removed_attachment_ids:
        _delete_screenshot_files(session_id, _unreferenced_attachment_ids(session, removed_attachment_ids))
    
    logger.info(f"更新消息: session={session_id}, message_id={message_id}")
    
    return {
        "success": True,
        "message": "消息更新成功"
    }


class BatchDeleteMessageRequest(BaseModel):
    """批量删除消息请求（使用消息 ID）"""
    message_ids: List[str]  # 要删除的消息 ID 列表


@router.post("/sessions/{session_id}/messages/delete")
async def delete_messages(session_id: str, request: BatchDeleteMessageRequest):
    """
    删除指定会话的消息（支持单条或多条）
    
    删除消息时会自动处理树形结构：
    - 从父消息的 children_ids 中移除
    - 递归删除所有子消息
    
    Args:
        session_id: 会话 ID
        request: 包含要删除的消息 ID 列表
    
    Returns:
        dict: 删除结果
    """
    session = session_storage.load_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if not request.message_ids:
        raise HTTPException(status_code=400, detail="未指定要删除的消息")
    
    # 收集所有需要删除的消息 ID（包括子消息）
    all_ids_to_delete = set()
    for msg_id in request.message_ids:
        all_ids_to_delete.update(collect_descendant_ids(session, msg_id))
        all_ids_to_delete.add(msg_id)
    
    # 从父消息的 children_ids 中移除
    for msg in session.messages:
        if msg.children_ids:
            msg.children_ids = [cid for cid in msg.children_ids if cid not in all_ids_to_delete]
    
    # 删除消息及其本地截图附件
    attachment_ids_to_delete = [
        attachment.id
        for msg in session.messages
        if msg.id in all_ids_to_delete
        for attachment in msg.attachments
    ]
    original_count = len(session.messages)
    session.messages = [msg for msg in session.messages if msg.id not in all_ids_to_delete]
    deleted_count = original_count - len(session.messages)
    _delete_screenshot_files(session_id, attachment_ids_to_delete)
    
    session.updated_at = int(time.time())
    session_storage.save_session(session)
    
    logger.info(f"删除消息: session={session_id}, count={deleted_count}, ids={request.message_ids}")
    
    return {
        "success": True,
        "message": f"成功删除 {deleted_count} 条消息"
    }


def collect_descendant_ids(session: Session, message_id: str) -> set:
    """
    递归收集消息的所有后代 ID
    
    Args:
        session: 会话对象
        message_id: 消息 ID
    
    Returns:
        set: 所有后代消息 ID
    """
    descendants = set()
    msg_dict = {msg.id: msg for msg in session.messages}
    
    if message_id not in msg_dict:
        return descendants
    
    msg = msg_dict[message_id]
    for child_id in msg.children_ids:
        descendants.add(child_id)
        descendants.update(collect_descendant_ids(session, child_id))
    
    return descendants


@router.get("/prompt-scenes")
async def get_prompt_scenes():
    from backend.services.prompt_scenes import load_catalog
    return load_catalog()


@router.put("/prompt-scenes")
async def put_prompt_scenes(catalog: SceneCatalog):
    from backend.services.prompt_scenes import save_catalog
    if len({scene.id for scene in catalog.scenes}) != len(catalog.scenes):
        raise HTTPException(status_code=400, detail="场景 ID 不能重复")
    save_catalog(catalog)
    return catalog


@router.put("/sessions/{session_id}/config")
async def update_session_config(session_id: str, config: SessionConfig):
    """
    更新会话配置（支持系统提示词和多模型并行选择）
    
    Args:
        session_id: 会话 ID
        config: 会话配置对象，包含：
            - source_name: 配置源名称
            - models: 选中的模型列表（支持多选）
            - temperature: 温度参数（0-2）
            - top_p: Top-p 采样参数（0-1）
            - system_prompt: 系统提示词（可选）
            - max_history_turns: 发送给模型的最近用户问题轮数（1-100）
            - include_assistant_history: 是否附带对应模型的历史回答
    
    Returns:
        dict: 更新结果和新配置
    
    Raises:
        HTTPException: 会话不存在时返回 404
    
    说明：
        - 系统提示词会影响该会话的所有后续回答
        - 多模型并行：选择多个模型后，每次发送消息会同时调用所有模型
        - 配置仅对当前会话生效，不影响其他会话
    """
    logger.info(f"更新会话配置: {session_id}")
    
    # 从磁盘加载会话
    session = session_storage.load_session(session_id)
    
    if not session:
        logger.warning(f"会话不存在: {session_id}")
        raise HTTPException(status_code=404, detail="会话不存在")

    if config.model_targets:
        for target in config.model_targets:
            source = next(
                (item for item in config_sources if item.name == target.source_name),
                None,
            )
            if not source or target.model not in source.models:
                raise HTTPException(
                    status_code=400,
                    detail=f"无效的模型配置: {target.source_name} · {target.model}",
                )
        first_source = config.model_targets[0].source_name
        config.source_name = first_source
        config.models = [
            target.model for target in config.model_targets
            if target.source_name == first_source
        ]
    
    previous_config = session.session_config
    if (config.active_scene and previous_config and previous_config.active_scene
            and previous_config.active_scene.id == config.active_scene.id
            and previous_config.active_scene != config.active_scene):
        from backend.services.prompt_scenes import load_catalog, save_catalog
        catalog = load_catalog()
        catalog.scenes = [config.active_scene if item.id == config.active_scene.id else item for item in catalog.scenes]
        save_catalog(catalog)

    generation_epochs[session_id] = uuid.uuid4().hex
    # 更新会话配置
    session.session_config = config
    session.updated_at = int(time.time())
    
    # 保存到磁盘
    if not session_storage.save_session(session):
        raise HTTPException(status_code=500, detail="保存会话配置失败")
    
    # 如果是当前会话，更新缓存（重要：必须更新，否则下次聊天会使用旧配置）
    global current_session_cache
    if session_id == current_session_id:
        current_session_cache = session
        logger.info(f"已更新当前会话缓存: {session_id}")
    
    logger.info(
        f"配置已更新: session={session_id}, "
        f"model_targets={[(target.source_name, target.model) for target in config.model_targets] or config.models}, "
        f"system_prompt={'已设置' if config.system_prompt else '未设置'}"
    )
    
    return {
        "success": True,
        "message": "会话配置已更新",
        "config": config.dict()
    }


class InsertSystemPromptRequest(BaseModel):
    """插入系统提示词请求"""
    parent_id: Optional[str] = None  # 在哪条消息之后插入（None 表示在末尾）
    content: str  # 系统提示词内容


@router.post("/sessions/{session_id}/system-prompt")
async def insert_system_prompt(session_id: str, request: InsertSystemPromptRequest):
    """
    在对话中插入动态系统提示词
    
    中途修改系统提示词时，会在指定位置插入一条 role: "system" 的消息
    这样可以实现在对话过程中改变 AI 的行为
    
    Args:
        session_id: 会话 ID
        request: 包含父消息 ID 和系统提示词内容
    
    Returns:
        dict: 插入的系统消息信息
    
    示例：
        在某条消息后插入："现在请用英语回答"
        后续对话会使用新的系统提示词
    """
    session = session_storage.load_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 生成系统消息 ID
    import uuid
    system_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    current_time = int(time.time())
    
    # 创建系统消息
    system_message = ChatMessage(
        id=system_msg_id,
        parent_id=request.parent_id,
        role="system",
        content=request.content,
        type="text",
        created_at=current_time,
        children_ids=[]
    )
    
    # 如果有父消息，更新父消息的 children_ids
    if request.parent_id:
        for msg in session.messages:
            if msg.id == request.parent_id:
                if system_msg_id not in msg.children_ids:
                    msg.children_ids.append(system_msg_id)
                break
    
    # 添加系统消息到会话
    session.messages.append(system_message)
    session.updated_at = current_time
    
    # 保存
    session_storage.save_session(session)
    
    # 如果是当前会话，更新缓存
    global current_session_cache
    if session_id == current_session_id and current_session_cache:
        current_session_cache = session
    
    logger.info(f"插入系统提示词: session={session_id}, parent_id={request.parent_id}")
    
    return {
        "success": True,
        "message": "系统提示词已插入",
        "system_message": system_message.dict()
    }


@router.get("/sessions/{session_id}/config")
async def get_session_config(session_id: str):
    """
    获取会话配置
    
    Args:
        session_id: 会话 ID
    
    Returns:
        dict: 包含会话配置（如果未设置则返回 None）
    
    Raises:
        HTTPException: 会话不存在时返回 404
    """
    logger.info(f"获取会话配置: {session_id}")
    
    session = session_storage.load_session(session_id)
    
    if not session:
        logger.warning(f"会话不存在: {session_id}")
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return {
        "success": True,
        "config": session.session_config.dict() if session.session_config else None
    }


@router.post("/sessions/{session_id}/messages/{message_id}/regenerate")
async def regenerate_message(session_id: str, message_id: str, request: RegenerateMessageRequest):
    """
    替换消息并重新生成响应
    
    此接口允许用户修改某条消息，并让模型基于新的消息内容重新生成响应
    会自动删除该消息之后的所有子消息，然后重新生成
    
    Args:
        session_id: 会话 ID
        message_id: 要替换的消息 ID
        request: 包含新消息内容和可选的模型选择
    
    Returns:
        StreamingResponse: 流式返回新的模型响应
    
    Raises:
        HTTPException: 会话或消息不存在，或其他错误
    
    流式响应格式（SSE）：
        - type: 'content' - 内容块
        - type: 'done' - 完成
        - type: 'error' - 错误
    """
    logger.info(f"重新生成消息: session={session_id}, message_id={message_id}")
    
    # 加载会话
    session = session_storage.load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 查找要替换的消息
    target_message = None
    target_index = -1
    for i, msg in enumerate(session.messages):
        if msg.id == message_id:
            target_message = msg
            target_index = i
            break
    
    if not target_message:
        raise HTTPException(status_code=404, detail="消息不存在")
    
    if target_message.role != "user":
        raise HTTPException(status_code=400, detail="只能重新生成用户消息的响应")
    
    if request.preserve_answer and (request.new_content != target_message.content or request.attachment_ids is not None):
        raise HTTPException(status_code=400, detail="场景重答必须保留原始问题和附件")

    generation_epoch = uuid.uuid4().hex
    generation_epochs[session_id] = generation_epoch

    def save_current_generation():
        if generation_epochs.get(session_id) != generation_epoch:
            raise asyncio.CancelledError()
        if not session_storage.save_session(session):
            raise RuntimeError("保存回答失败")

    session_config = session.session_config
    context_settings = resolve_chat_context_config(session_config)
    model_targets = resolve_model_targets(session_config, request.model)
    if request.reasoning_effort is not None:
        if len(model_targets) != 1:
            raise HTTPException(status_code=400, detail="请选择单个模型后设置本次思考强度")
        model_targets[0]["reasoning_effort"] = request.reasoning_effort
    models_to_use = [target["model"] for target in model_targets]

    replacement_attachments = (
        _load_message_attachments(session_id, request.attachment_ids)
        if request.attachment_ids is not None else None
    )
    removed_attachment_ids = []
    if replacement_attachments is not None:
        new_ids = {attachment.id for attachment in replacement_attachments}
        removed_attachment_ids = [attachment.id for attachment in target_message.attachments if attachment.id not in new_ids]
        existing = {attachment.id: attachment for attachment in target_message.attachments}
        target_message.attachments = [existing.get(attachment.id, attachment) for attachment in replacement_attachments]
        target_message.type = "image" if replacement_attachments else "text"

    # A model-only rerun keeps the other answers and the later conversation.
    existing_assistant = next((
        msg for msg in session.messages
        if msg.id in target_message.children_ids and msg.role == "assistant"
    ), None)
    selected_target = model_targets[0] if len(model_targets) == 1 else None
    existing_model_entry = None
    if existing_assistant and selected_target and existing_assistant.parallel_models:
        existing_model_entry = next((
            entry for entry in existing_assistant.parallel_models
            if entry.get("model_key") == selected_target["key"]
            or (
                entry.get("model_info", {}).get("name") == selected_target["model"]
                and entry.get("model_info", {}).get("provider") == selected_target["source_name"]
            )
        ), None)
    targeted_rerun = bool(
        request.model and request.reasoning_effort is not None
        and request.new_content == target_message.content
        and request.attachment_ids is None
        and existing_assistant
        and (existing_model_entry or (
            existing_assistant.model_info
            and existing_assistant.model_info.name == selected_target["model"]
            and existing_assistant.model_info.provider == selected_target["source_name"]
        ))
    )
    if request.model and request.reasoning_effort is not None and not targeted_rerun:
        raise HTTPException(status_code=409, detail="目标模型的原回答已变化，请刷新消息后重试")

    if request.preserve_answer:
        for answer in session.messages:
            if answer.id in target_message.children_ids and answer.role == "assistant":
                target_message.answer_versions.append(answer.dict(exclude={"answer_versions"}))

    # 更新消息内容
    target_message.content = request.new_content
    target_message.created_at = int(time.time())
    
    # 只删除目标消息的直接子消息（即 AI 的回答），保留后续对话
    # 收集要删除的直接子消息和它们的子消息信息
    direct_children_to_delete = [] if targeted_rerun else list(target_message.children_ids)
    grandchildren_ids = []  # 孙子消息（后续对话的第一条）
    
    # 创建消息ID到消息的映射
    msg_dict = {msg.id: msg for msg in session.messages}
    
    # 收集孙子消息（被删除消息的子消息）
    for child_id in direct_children_to_delete:
        if child_id in msg_dict:
            child_msg = msg_dict[child_id]
            grandchildren_ids.extend(child_msg.children_ids)
    
    logger.info(f"删除 {len(direct_children_to_delete)} 条直接回复，保留 {len(grandchildren_ids)} 条后续消息")
    
    # 清空目标消息的子消息列表（稍后会添加新的回答）
    if not targeted_rerun:
        target_message.children_ids = []
    
    # 从会话中删除直接子消息
    session.messages = [msg for msg in session.messages if msg.id not in direct_children_to_delete]
    
    # 找到目标消息在数组中的索引
    target_index_after_delete = -1
    for i, msg in enumerate(session.messages):
        if msg.id == message_id:
            target_index_after_delete = i
            break
    
    logger.info(f"删除后，目标消息索引: {target_index_after_delete}")
    
    # 保存会话
    session.updated_at = int(time.time())
    save_current_generation()
    if removed_attachment_ids:
        _delete_screenshot_files(session_id, _unreferenced_attachment_ids(session, removed_attachment_ids))
    
    # 构建消息历史（到目标消息为止）
    messages_history = build_message_path(session, message_id)
    
    logger.info(f"构建消息历史: {len(messages_history)} 条消息")
    
    def build_messages_for_model_regenerate(
        target_model: str,
        target_source_name: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        为重新生成构建特定模型的消息历史
        
        Args:
            target_model: 目标模型名称
            
        Returns:
            List[Dict[str, str]]: OpenAI 格式的消息列表
        """
        api_messages = []
        
        # 1. 添加 system prompt（如果有）
        system_prompt = compose_session_system_prompt(session)
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        
        # 2. 只保留最近 N 轮用户问题；assistant 历史按配置决定是否加入。
        # Keep the target question outside both history limits and packaging.
        prior_history = [msg for msg in messages_history if msg.id != message_id]
        selected_history = prior_history
        user_indexes = [
            index for index, msg in enumerate(prior_history)
            if msg.role == "user"
        ]
        max_history_turns = context_settings["max_history_turns"]
        if user_indexes and len(user_indexes) > max_history_turns:
            selected_history = prior_history[user_indexes[-max_history_turns]:]

        include_assistant = context_settings["include_assistant_history"]
        for msg in selected_history:
            if msg.role == 'user':
                api_messages.append({"role": "user", "content": msg.content})
            elif msg.role == 'assistant' and include_assistant:
                # assistant 消息：只添加当前模型的回复
                assistant_content = None
                
                # 检查是否是并行响应
                if msg.is_parallel_response and msg.parallel_models:
                    # 并行响应：从 parallel_models 中找到当前模型的回复
                    for model_data in msg.parallel_models:
                        model_info = model_data.get('model_info', {})
                        same_model = (
                            model_data.get('model') == target_model
                            or model_info.get('name') == target_model
                        )
                        same_source = (
                            not target_source_name
                            or not model_info.get('provider')
                            or model_info.get('provider') == target_source_name
                        )
                        if same_model and same_source:
                            assistant_content = model_data.get('content', '')
                            break
                else:
                    # 单模型响应：检查是否是当前模型
                    if (
                        msg.model_info
                        and msg.model_info.name == target_model
                        and (
                            not target_source_name
                            or not msg.model_info.provider
                            or msg.model_info.provider == target_source_name
                        )
                    ):
                        assistant_content = msg.content
                    elif not msg.model_info:
                        # 如果没有 model_info，说明是旧数据，直接使用
                        assistant_content = msg.content
                
                # 添加 assistant 消息（如果找到了对应模型的回复）
                if assistant_content is not None:
                    api_messages.append({"role": "assistant", "content": assistant_content})

        api_messages = trim_history_context(
            api_messages, context_settings["max_history_chars"], target_model
        )
        
        rendered_user_prompt = render_session_user_prompt(
            session, target_message.content
        )
        scoped_messages = build_scoped_request(
            api_messages, rendered_user_prompt, include_assistant
        )
        if target_message.attachments:
            scoped_messages[-1]["content"] = _multimodal_user_content(
                session.id,
                scoped_messages[-1]["content"],
                target_message.attachments,
            )
        return scoped_messages
    
    async def generate():
        tasks = []
        import asyncio
        import uuid
        
        try:
            is_parallel = len(models_to_use) > 1
            logger.info(f"开始重新生成: models={models_to_use}, parallel={is_parallel}")
            
            # 准备配置信息用于日志记录
            config_info = {
                "temperature": session_config.temperature if session_config else 0.7,
                "top_p": session_config.top_p if session_config else 1.0
            }
            
            if is_parallel:
                # 多模型并行调用
                yield f"data: {json.dumps({'type': 'multi_model_start', 'models': models_to_use, 'targets': public_model_targets(model_targets)}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)
                
                assistant_messages = []
                model_results = {}
                model_messages_map = {}  # 存储每个模型的消息历史（用于日志记录）
                
                for model_index, target in enumerate(model_targets):
                    model_name = target['model']
                    yield f"data: {json.dumps({'type': 'model_start', 'model_index': model_index, 'model': model_name, 'model_key': target['key'], 'source_name': target['source_name']}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0)
                    model_results[model_index] = {
                        'content': '',
                        'start_time': time.time(),
                        'model': model_name,
                        'model_key': target['key'],
                        'source_name': target['source_name'],
                        'reasoning_effort': target['reasoning_effort'],
                    }
                
                chunk_queue = asyncio.Queue()
                
                async def stream_model(model_index: int, target: Dict[str, Any]):
                    model_name = target['model']
                    source = target['source']
                    try:
                        # 为当前模型构建专属的消息历史
                        model_messages = build_messages_for_model_regenerate(
                            model_name, target['source_name']
                        )
                        logger.info(f"🔧 重新生成 - 模型 {target['key']} 的消息历史: {len(model_messages)} 条")
                        log_model_request_context(
                            target['key'],
                            model_messages,
                            label="重新生成",
                            context_settings=context_settings,
                        )
                        
                        # 保存消息历史用于日志记录
                        model_messages_map[target['key']] = model_messages
                        
                        client = AsyncOpenAI(
                            api_key=source.api_key,
                            base_url=source.base_url
                        )
                        
                        request_params = dict(
                            model=model_name,
                            messages=model_messages,
                            temperature=session_config.temperature if session_config else 0.7,
                            top_p=session_config.top_p if session_config else 1.0,
                            stream=True,
                            **get_chat_completion_extra_params(
                                source, model_name, target['reasoning_effort']
                            )
                        )
                        request_preview = log_provider_request(source, request_params)
                        await chunk_queue.put({
                            "type": "provider_request",
                            "stage": "regenerate",
                            "model_key": target["key"],
                            "request": request_preview,
                        })
                        stream = await client.chat.completions.create(**request_params)
                        
                        chunk_count = 0
                        async for chunk in stream:
                            if not chunk.choices:
                                continue
                            content = chunk.choices[0].delta.content
                            if content:
                                model_results[model_index]['content'] += content
                                chunk_count += 1
                                
                                await chunk_queue.put({
                                    'type': 'content',
                                    'model_index': model_index,
                                    'model': model_name,
                                    'model_key': target['key'],
                                    'source_name': target['source_name'],
                                    'data': content
                                })
                        
                        latency_ms = int((time.time() - model_results[model_index]['start_time']) * 1000)
                        logger.info(f"模型 {model_name} 完成: {len(model_results[model_index]['content'])} 字符")
                        
                        await chunk_queue.put({
                            'type': 'model_done',
                            'model_index': model_index,
                            'model': model_name,
                            'model_key': target['key'],
                            'source_name': target['source_name'],
                            'latency_ms': latency_ms
                        })
                        
                    except Exception as e:
                        logger.error(f"模型 {model_name} 调用失败: {e}")
                        await chunk_queue.put({
                            'type': 'model_error',
                            'model_index': model_index,
                            'model': model_name,
                            'model_key': target['key'],
                            'source_name': target['source_name'],
                            'message': str(e)
                        })
                
                tasks = []
                for model_index, target in enumerate(model_targets):
                    task = asyncio.create_task(stream_model(model_index, target))
                    tasks.append(task)
                
                completed_models = 0
                while completed_models < len(models_to_use):
                    try:
                        chunk_data = await asyncio.wait_for(chunk_queue.get(), timeout=60.0)
                        yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
                        await asyncio.sleep(0)
                        
                        if chunk_data['type'] in ['model_done', 'model_error']:
                            completed_models += 1
                            
                    except asyncio.TimeoutError:
                        logger.error("等待模型响应超时")
                        break
                
                await asyncio.gather(*tasks, return_exceptions=True)
                
                for model_index, result in model_results.items():
                    if result['content']:
                        assistant_messages.append({
                            'model': result['model'],
                            'model_key': result['model_key'],
                            'source_name': result['source_name'],
                            'reasoning_effort': result['reasoning_effort'],
                            'content': result['content'],
                            'latency_ms': int((time.time() - result['start_time']) * 1000)
                        })
                
                # 保存多模型响应
                assistant_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
                assistant_msg_time = int(time.time())
                
                parallel_models_data = []
                for model_data in assistant_messages:
                    parallel_models_data.append({
                        "model": model_data['model'],
                        "model_key": model_data['model_key'],
                        "source_name": model_data['source_name'],
                        "content": model_data['content'],
                        "latency_ms": model_data['latency_ms'],
                        "model_info": {
                            "id": model_data['model_key'],
                            "name": model_data['model'],
                            "provider": model_data['source_name'],
                            "reasoning_effort": model_data['reasoning_effort'],
                        }
                    })
                
                assistant_msg = ChatMessage(
                    id=assistant_msg_id,
                    parent_id=message_id,
                    role="assistant",
                    scene_name=session_config.active_scene.name if session_config and session_config.active_scene else None,
                    content="",
                    type="multi_model",
                    created_at=assistant_msg_time,
                    children_ids=[],
                    is_parallel_response=True,
                    parallel_models=parallel_models_data
                )
                
                target_message.children_ids.append(assistant_msg_id)
                
                # 将后续对话（孙子消息）链接到新的回答
                if grandchildren_ids:
                    assistant_msg.children_ids = grandchildren_ids
                    # 更新孙子消息的 parent_id
                    for gc_id in grandchildren_ids:
                        for msg in session.messages:
                            if msg.id == gc_id:
                                msg.parent_id = assistant_msg_id
                                break
                    logger.info(f"将 {len(grandchildren_ids)} 条后续消息链接到新回答")
                
                # 在目标消息后面插入新消息（而不是 append 到末尾）
                insert_position = target_index_after_delete + 1
                session.messages.insert(insert_position, assistant_msg)
                logger.info(f"新消息插入到位置 {insert_position}")
                
                session.updated_at = int(time.time())
                save_current_generation()
                
                # 记录每个模型的交互
                for model_data in parallel_models_data:
                    model_name = model_data['model_info']['name']
                    # 使用保存的消息历史（调用 API 时的消息）
                    model_messages = model_messages_map.get(model_data['model_key'], [])
                    log_model_interaction(
                        session_id=session_id,
                        model=model_data['model_key'],
                        messages=model_messages,
                        response=model_data['content'],
                        elapsed_time=model_data['latency_ms'] / 1000.0,
                        config=config_info
                    )
                
                logger.info(f"多模型回复完成并保存，共 {len(assistant_messages)} 个模型")
                
                yield f"data: {json.dumps({'type': 'done', 'model_count': len(assistant_messages)}, ensure_ascii=False)}\n\n"
                
            else:
                # 单模型模式
                target = model_targets[0]
                model_to_use = target['model']
                source_to_use = target['source']
                start_time = time.time()
                
                # 为当前模型构建专属的消息历史
                model_messages = build_messages_for_model_regenerate(
                    model_to_use, target['source_name']
                )
                logger.info(f"🔧 重新生成 - 模型 {model_to_use} 的消息历史: {len(model_messages)} 条")
                log_model_request_context(
                    model_to_use,
                    model_messages,
                    label="重新生成",
                    context_settings=context_settings,
                )
                
                client = OpenAI(
                    api_key=source_to_use.api_key,
                    base_url=source_to_use.base_url
                )
                
                request_params = dict(
                    model=model_to_use,
                    messages=model_messages,
                    temperature=session_config.temperature if session_config else 0.7,
                    top_p=session_config.top_p if session_config else 1.0,
                    stream=True,
                    **get_chat_completion_extra_params(
                        source_to_use, model_to_use, target['reasoning_effort']
                    )
                )
                request_preview = log_provider_request(source_to_use, request_params)
                yield f"data: {json.dumps({'type': 'provider_request', 'stage': 'regenerate', 'model_key': target['key'], 'request': request_preview}, ensure_ascii=False)}\n\n"
                stream = await asyncio.to_thread(client.chat.completions.create, **request_params)
                
                assistant_message = ''
                chunk_count = 0
                
                async for chunk in iterate_provider_stream(stream):
                    if not chunk.choices:
                        continue
                    content = chunk.choices[0].delta.content
                    if content:
                        assistant_message += content
                        chunk_count += 1
                        
                        chunk_data = f"data: {json.dumps({'type': 'content', 'data': content}, ensure_ascii=False)}\n\n"
                        yield chunk_data
                        await asyncio.sleep(0)
                
                latency_ms = int((time.time() - start_time) * 1000)
                logger.info(f"流式发送完成: {chunk_count} 个chunks")

                if targeted_rerun:
                    if existing_model_entry is not None:
                        existing_model_entry["content"] = assistant_message
                        existing_model_entry["latency_ms"] = latency_ms
                        existing_model_entry.setdefault("model_info", {})["reasoning_effort"] = target['reasoning_effort']
                    else:
                        existing_assistant.content = assistant_message
                        existing_assistant.latency_ms = latency_ms
                        existing_assistant.model_info.reasoning_effort = target['reasoning_effort']
                    session.updated_at = int(time.time())
                    save_current_generation()
                    yield f"data: {json.dumps({'type': 'done', 'message_id': existing_assistant.id}, ensure_ascii=False)}\n\n"
                    return
                
                # 记录模型交互
                log_model_interaction(
                    session_id=session_id,
                    model=model_to_use,
                    messages=model_messages,
                    response=assistant_message,
                    elapsed_time=latency_ms / 1000.0,
                    config=config_info
                )
                
                # 生成 assistant 消息
                assistant_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
                assistant_msg_time = int(time.time())
                
                assistant_msg = ChatMessage(
                    id=assistant_msg_id,
                    parent_id=message_id,
                    role="assistant",
                    scene_name=session_config.active_scene.name if session_config and session_config.active_scene else None,
                    content=assistant_message,
                    type="text",
                    created_at=assistant_msg_time,
                    children_ids=[],
                    model_info={
                        "id": target['key'],
                        "name": model_to_use,
                        "provider": source_to_use.name if source_to_use else "unknown",
                        "reasoning_effort": target['reasoning_effort'],
                    },
                    usage={
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0
                    },
                    status="success",
                    latency_ms=latency_ms
                )
                
                target_message.children_ids.append(assistant_msg_id)
                
                # 将后续对话（孙子消息）链接到新的回答
                if grandchildren_ids:
                    assistant_msg.children_ids = grandchildren_ids
                    # 更新孙子消息的 parent_id
                    for gc_id in grandchildren_ids:
                        for msg in session.messages:
                            if msg.id == gc_id:
                                msg.parent_id = assistant_msg_id
                                break
                    logger.info(f"将 {len(grandchildren_ids)} 条后续消息链接到新回答")
                
                # 在目标消息后面插入新消息（而不是 append 到末尾）
                insert_position = target_index_after_delete + 1
                session.messages.insert(insert_position, assistant_msg)
                logger.info(f"新消息插入到位置 {insert_position}")
                
                session.updated_at = assistant_msg_time
                
                save_current_generation()
                
                logger.info(f"AI 回复完成并保存，总长度: {len(assistant_message)}")
                
                done_data = {'type': 'done', 'message_id': assistant_msg_id}
                yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"重新生成失败: {e}", exc_info=True)
            # 记录错误
            if 'models_to_use' in locals() and 'api_messages' in locals():
                for model in [target['key'] for target in model_targets]:
                    log_error(
                        session_id=session_id,
                        model=model,
                        messages=api_messages,
                        error=e,
                        stage="regenerate"
                    )
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    
    return StreamingResponse(
        generate(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
