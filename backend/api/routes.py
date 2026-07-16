"""
API 路由定义
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.api.models import (
    ConfigModel,
    ConfigSource,
    ConfigList,
    ChatRequest, 
    ChatResponse,
    RecordingResponse,
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
    TokenUsage
)
from backend.services.audio_recorder import AudioRecorder
from backend.services.voice_recognizer import VoiceRecognizer
from backend.services.streaming_asr import StreamingASR
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
    from config import OPENAI_CONFIG, DEFAULT_CONFIG_NAME
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

logger = get_api_logger()

# 创建路由器
router = APIRouter()

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
            if source.api_key:
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


def get_chat_completion_extra_params(source: Optional[ConfigSource], model: str) -> Dict[str, Any]:
    """Return provider-specific Chat Completions options."""
    source_name = (source.name if source else "").lower()
    base_url = (source.base_url if source else api_config.base_url).lower()
    model_name = (model or "").lower()
    
    if (
        source_name == "qwen"
        or "dashscope.aliyuncs.com" in base_url
        or model_name.startswith("qwen")
    ):
        return {"extra_body": {"enable_thinking": False}}
    
    return {}

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
        session_config=SessionConfig()  # 使用默认配置
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


@router.post("/recording/start")
async def start_recording():
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
            try:
                await streaming_asr.stop_streaming()
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
            except:
                pass
        # 注意：这里不设置 streaming_asr = None，保持原有状态
        
        return RecordingResponse(success=False, message=str(e))


@router.get("/recording/status")
async def get_recording_status():
    """获取录音状态"""
    global streaming_asr
    
    if not streaming_asr:
        return {"is_recording": False, "auto_stopped": False}
    
    return {
        "is_recording": streaming_asr.is_recording,
        "auto_stopped": streaming_asr.auto_stopped
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


@router.post("/chat")
async def chat(request: ChatRequest):
    """发送消息（流式返回）- 支持树形对话和并行响应"""
    if not request.message:
        raise HTTPException(status_code=400, detail="消息不能为空")
    
    logger.info(f"收到聊天请求: {request.message[:50]}...")
    
    # 获取当前会话
    current_session = get_current_session()
    session_config = current_session.session_config
    
    if session_config and session_config.models and len(session_config.models) > 0:
        models_to_use = session_config.models
        source_name = session_config.source_name or current_config.current_source
        source_to_use = next((s for s in config_sources if s.name == source_name), None)
    else:
        models_to_use = [api_config.model]
        source_name = current_config.current_source
        source_to_use = next((s for s in config_sources if s.name == source_name), None)
    
    if not source_to_use:
        logger.error(f"配置源不存在: source={source_name}, models={models_to_use}")
        raise HTTPException(status_code=400, detail=f"配置源 {source_name} 不存在")
    
    if not source_to_use.api_key:
        logger.error(f"API Key 未配置: source={source_to_use.name}, models={models_to_use}")
        raise HTTPException(status_code=400, detail=f"请先配置 {source_to_use.name} 的 API Key")
    
    # 生成用户消息 ID
    import uuid
    user_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    current_time = int(time.time())
    
    # 创建用户消息（树形结构）
    user_message = ChatMessage(
        id=user_msg_id,
        parent_id=request.parent_id,  # 从请求中获取父消息 ID
        role="user",
        content=request.message,
        type="text",
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
    
    def build_messages_for_model(target_model: str) -> List[Dict[str, str]]:
        """
        为特定模型构建消息历史
        
        Args:
            target_model: 目标模型名称
            
        Returns:
            List[Dict[str, str]]: OpenAI 格式的消息列表
        """
        api_messages = []
        
        # 1. 添加 system prompt（如果有）
        system_prompt = None
        if current_session.session_config and current_session.session_config.system_prompt:
            system_prompt = current_session.session_config.system_prompt
        elif current_session.system_prompt:
            system_prompt = current_session.system_prompt
        
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        
        # 2. 遍历历史消息，构建上下文
        # 排除最后一条（刚添加的用户消息）
        for msg in current_session.messages[:-1]:
            if msg.role == 'user':
                # 用户消息：所有模型都需要
                api_messages.append({"role": "user", "content": msg.content})
            elif msg.role == 'assistant':
                # assistant 消息：只添加当前模型的回复
                assistant_content = None
                
                # 检查是否是并行响应
                if msg.is_parallel_response and msg.parallel_models:
                    # 并行响应：从 parallel_models 中找到当前模型的回复
                    for model_data in msg.parallel_models:
                        if model_data.get('model') == target_model or model_data.get('model_info', {}).get('name') == target_model:
                            assistant_content = model_data.get('content', '')
                            break
                else:
                    # 单模型响应：检查是否是当前模型
                    if msg.model_info and msg.model_info.name == target_model:
                        assistant_content = msg.content
                    elif not msg.model_info:
                        # 如果没有 model_info，说明是旧数据，直接使用
                        assistant_content = msg.content
                
                # 添加 assistant 消息（如果找到了对应模型的回复）
                if assistant_content is not None:
                    api_messages.append({"role": "assistant", "content": assistant_content})
        
        # 3. 添加当前用户消息
        api_messages.append({"role": "user", "content": user_message.content})
        
        return api_messages
    
    async def generate():
        import asyncio
        try:
            logger.info(f"📝 会话总消息数: {len(current_session.messages)}")
            is_parallel = len(models_to_use) > 1
            logger.info(f"🚀 开始流式调用: models={models_to_use}, parallel={is_parallel}, session={current_session_id}")
            
            # 准备配置信息用于日志记录
            config_info = {
                "temperature": session_config.temperature if session_config else 0.7,
                "top_p": session_config.top_p if session_config else 1.0
            }
            
            if is_parallel:
                # 多模型并行调用模式（真正的并行流式输出）
                yield f"data: {json.dumps({'type': 'multi_model_start', 'models': models_to_use}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)
                
                assistant_messages = []  # 存储所有模型的响应
                model_results = {}  # 存储每个模型的完整响应
                model_messages_map = {}  # 存储每个模型的消息历史（用于日志记录）
                
                # 为每个模型发送开始标记
                for model_index, model_name in enumerate(models_to_use):
                    yield f"data: {json.dumps({'type': 'model_start', 'model_index': model_index, 'model': model_name}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0)
                    model_results[model_index] = {'content': '', 'start_time': time.time(), 'model': model_name}
                
                logger.info(f"🚀 并行调用 {len(models_to_use)} 个模型")
                
                # 创建队列接收来自所有模型的 chunks
                chunk_queue = asyncio.Queue()
                
                # 定义单个模型的流式处理任务
                async def stream_model(model_index: int, model_name: str):
                    try:
                        # 为当前模型构建专属的消息历史
                        model_messages = build_messages_for_model(model_name)
                        logger.info(f"🔧 模型 {model_name} 的消息历史: {len(model_messages)} 条")
                        
                        # 保存消息历史用于日志记录
                        model_messages_map[model_name] = model_messages
                        
                        # 创建异步客户端
                        client = AsyncOpenAI(
                            api_key=source_to_use.api_key if source_to_use else api_config.api_key,
                            base_url=source_to_use.base_url if source_to_use else api_config.base_url
                        )
                        
                        # 异步调用模型（流式）
                        stream = await client.chat.completions.create(
                            model=model_name,
                            messages=model_messages,
                            temperature=session_config.temperature if session_config else 0.7,
                            top_p=session_config.top_p if session_config else 1.0,
                            stream=True,
                            **get_chat_completion_extra_params(source_to_use, model_name)
                        )
                        
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
                                    'data': content
                                })
                        
                        latency_ms = int((time.time() - model_results[model_index]['start_time']) * 1000)
                        logger.info(f"✅ 模型 {model_name} 完成: {len(model_results[model_index]['content'])} 字符, {chunk_count} chunks, 耗时 {latency_ms}ms")
                        
                        # 发送完成标记
                        await chunk_queue.put({
                            'type': 'model_done',
                            'model_index': model_index,
                            'model': model_name,
                            'latency_ms': latency_ms
                        })
                        
                    except Exception as e:
                        logger.error(f"❌ 模型 {model_name} 调用失败: {e}")
                        await chunk_queue.put({
                            'type': 'model_error',
                            'model_index': model_index,
                            'model': model_name,
                            'message': str(e)
                        })
                
                # 启动所有模型的并行任务
                tasks = []
                for model_index, model_name in enumerate(models_to_use):
                    task = asyncio.create_task(stream_model(model_index, model_name))
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
                        "content": model_data['content'],
                        "latency_ms": model_data['latency_ms'],
                        "model_info": {
                            "id": model_data['model'],
                            "name": model_data['model'],
                            "provider": source_to_use.name if source_to_use else "unknown"
                        }
                    })
                
                # 创建一个多模型容器消息
                assistant_msg = ChatMessage(
                    id=assistant_msg_id,
                    parent_id=user_msg_id,
                    role="assistant",
                    content="",  # 容器消息内容为空
                    type="multi_model",  # 标记为多模型类型
                    created_at=assistant_msg_time,
                    children_ids=[],
                    is_parallel_response=True,
                    parallel_models=parallel_models_data  # 保存所有模型的响应
                )
                
                user_message.children_ids.append(assistant_msg_id)
                current_session.messages.append(assistant_msg)
                
                current_session.updated_at = int(time.time())
                save_current_session()
                
                # 记录每个模型的交互
                for idx, model_data in enumerate(parallel_models_data):
                    model_name = model_data['model_info']['name']
                    # 使用保存的消息历史（调用 API 时的消息）
                    model_messages = model_messages_map.get(model_name, [])
                    log_model_interaction(
                        session_id=current_session_id,
                        model=model_name,
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
                model_to_use = models_to_use[0]
                start_time = time.time()
                
                # 为当前模型构建专属的消息历史
                model_messages = build_messages_for_model(model_to_use)
                logger.info(f"🔧 模型 {model_to_use} 的消息历史: {len(model_messages)} 条")
                
                client = OpenAI(
                    api_key=source_to_use.api_key,
                    base_url=source_to_use.base_url
                )
                
                # 调用 OpenAI API（流式）
                stream = client.chat.completions.create(
                    model=model_to_use,
                    messages=model_messages,
                    temperature=session_config.temperature if session_config else 0.7,
                    top_p=session_config.top_p if session_config else 1.0,
                    stream=True,
                    **get_chat_completion_extra_params(source_to_use, model_to_use)
                )
                
                assistant_message = ''
                chunk_count = 0
                last_log_time = time.time()
                
                for chunk in stream:
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
                    session_id=current_session_id,
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
                    content=assistant_message,
                    type="text",
                    created_at=assistant_msg_time,
                    children_ids=[],
                    model_info={
                        "id": model_to_use,
                        "name": model_to_use,
                        "provider": source_to_use.name if source_to_use else "unknown"
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
                user_message.children_ids.append(assistant_msg_id)
                
                # 添加助手消息到当前会话
                current_session.messages.append(assistant_msg)
                current_session.updated_at = assistant_msg_time
                
                # 保存到存储
                save_current_session()
                
                logger.info(f"💾 AI 回复完成并保存，总长度: {len(assistant_message)}, session={current_session_id}")
                
                # 发送完成信号（包含消息 ID）
                done_data = {'type': 'done', 'message_id': assistant_msg_id}
                yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"❌ AI 调用出错: {e}", exc_info=True)
            # 记录错误
            if 'models_to_use' in locals() and 'api_messages' in locals():
                for model in models_to_use:
                    log_error(
                        session_id=current_session_id,
                        model=model,
                        messages=api_messages,
                        error=e,
                        stage="streaming"
                    )
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
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
            session_config=SessionConfig()  # 使用默认配置
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
    
    # 查找消息
    message_found = False
    for msg in session.messages:
        if msg.id == message_id:
            msg.content = request.content
            msg.created_at = int(time.time())  # 更新时间戳
            message_found = True
            break
    
    if not message_found:
        raise HTTPException(status_code=404, detail="消息不存在")
    
    session.updated_at = int(time.time())
    session_storage.save_session(session)
    
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
    
    # 删除消息
    original_count = len(session.messages)
    session.messages = [msg for msg in session.messages if msg.id not in all_ids_to_delete]
    deleted_count = original_count - len(session.messages)
    
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
    
    # 更新会话配置
    session.session_config = config
    session.updated_at = int(time.time())
    
    # 保存到磁盘
    session_storage.save_session(session)
    
    # 如果是当前会话，更新缓存（重要：必须更新，否则下次聊天会使用旧配置）
    global current_session_cache
    if session_id == current_session_id:
        current_session_cache = session
        logger.info(f"已更新当前会话缓存: {session_id}")
    
    logger.info(
        f"配置已更新: session={session_id}, "
        f"models={config.models}, "
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
    
    session_config = session.session_config
    if request.model:
        models_to_use = [request.model]
        source_to_use = next((s for s in config_sources if request.model in s.models), None)
        source_name = source_to_use.name if source_to_use else None
    elif session_config and session_config.models and len(session_config.models) > 0:
        models_to_use = session_config.models
        source_name = session_config.source_name or current_config.current_source
        source_to_use = next((s for s in config_sources if s.name == source_name), None)
    else:
        models_to_use = [api_config.model]
        source_name = current_config.current_source
        source_to_use = next((s for s in config_sources if s.name == source_name), None)
    
    if not source_to_use:
        logger.error(f"配置源不存在: source={source_name}, models={models_to_use}")
        raise HTTPException(status_code=400, detail=f"配置源 {source_name or '未知'} 不存在")
    
    if not source_to_use.api_key:
        logger.error(f"API Key 未配置: source={source_to_use.name}, models={models_to_use}")
        raise HTTPException(status_code=400, detail=f"请先配置 {source_to_use.name} 的 API Key")
    
    # 更新消息内容
    target_message.content = request.new_content
    target_message.created_at = int(time.time())
    
    # 只删除目标消息的直接子消息（即 AI 的回答），保留后续对话
    # 收集要删除的直接子消息和它们的子消息信息
    direct_children_to_delete = list(target_message.children_ids)  # 直接子消息（回答）
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
    session_storage.save_session(session)
    
    # 构建消息历史（到目标消息为止）
    messages_history = build_message_path(session, message_id)
    
    logger.info(f"构建消息历史: {len(messages_history)} 条消息")
    
    def build_messages_for_model_regenerate(target_model: str) -> List[Dict[str, str]]:
        """
        为重新生成构建特定模型的消息历史
        
        Args:
            target_model: 目标模型名称
            
        Returns:
            List[Dict[str, str]]: OpenAI 格式的消息列表
        """
        api_messages = []
        
        # 1. 添加 system prompt（如果有）
        system_prompt = None
        if session.session_config and session.session_config.system_prompt:
            system_prompt = session.session_config.system_prompt
        elif session.system_prompt:
            system_prompt = session.system_prompt
        
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        
        # 2. 遍历历史消息，构建上下文
        for msg in messages_history:
            if msg.role == 'user':
                # 用户消息：所有模型都需要
                api_messages.append({"role": "user", "content": msg.content})
            elif msg.role == 'assistant':
                # assistant 消息：只添加当前模型的回复
                assistant_content = None
                
                # 检查是否是并行响应
                if msg.is_parallel_response and msg.parallel_models:
                    # 并行响应：从 parallel_models 中找到当前模型的回复
                    for model_data in msg.parallel_models:
                        if model_data.get('model') == target_model or model_data.get('model_info', {}).get('name') == target_model:
                            assistant_content = model_data.get('content', '')
                            break
                else:
                    # 单模型响应：检查是否是当前模型
                    if msg.model_info and msg.model_info.name == target_model:
                        assistant_content = msg.content
                    elif not msg.model_info:
                        # 如果没有 model_info，说明是旧数据，直接使用
                        assistant_content = msg.content
                
                # 添加 assistant 消息（如果找到了对应模型的回复）
                if assistant_content is not None:
                    api_messages.append({"role": "assistant", "content": assistant_content})
        
        return api_messages
    
    async def generate():
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
                yield f"data: {json.dumps({'type': 'multi_model_start', 'models': models_to_use}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)
                
                assistant_messages = []
                model_results = {}
                model_messages_map = {}  # 存储每个模型的消息历史（用于日志记录）
                
                for model_index, model_name in enumerate(models_to_use):
                    yield f"data: {json.dumps({'type': 'model_start', 'model_index': model_index, 'model': model_name}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0)
                    model_results[model_index] = {'content': '', 'start_time': time.time(), 'model': model_name}
                
                chunk_queue = asyncio.Queue()
                
                async def stream_model(model_index: int, model_name: str):
                    try:
                        # 为当前模型构建专属的消息历史
                        model_messages = build_messages_for_model_regenerate(model_name)
                        logger.info(f"🔧 重新生成 - 模型 {model_name} 的消息历史: {len(model_messages)} 条")
                        
                        # 保存消息历史用于日志记录
                        model_messages_map[model_name] = model_messages
                        
                        client = AsyncOpenAI(
                            api_key=source_to_use.api_key if source_to_use else api_config.api_key,
                            base_url=source_to_use.base_url if source_to_use else api_config.base_url
                        )
                        
                        stream = await client.chat.completions.create(
                            model=model_name,
                            messages=model_messages,
                            temperature=session_config.temperature if session_config else 0.7,
                            top_p=session_config.top_p if session_config else 1.0,
                            stream=True,
                            **get_chat_completion_extra_params(source_to_use, model_name)
                        )
                        
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
                                    'data': content
                                })
                        
                        latency_ms = int((time.time() - model_results[model_index]['start_time']) * 1000)
                        logger.info(f"模型 {model_name} 完成: {len(model_results[model_index]['content'])} 字符")
                        
                        await chunk_queue.put({
                            'type': 'model_done',
                            'model_index': model_index,
                            'model': model_name,
                            'latency_ms': latency_ms
                        })
                        
                    except Exception as e:
                        logger.error(f"模型 {model_name} 调用失败: {e}")
                        await chunk_queue.put({
                            'type': 'model_error',
                            'model_index': model_index,
                            'model': model_name,
                            'message': str(e)
                        })
                
                tasks = []
                for model_index, model_name in enumerate(models_to_use):
                    task = asyncio.create_task(stream_model(model_index, model_name))
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
                        "content": model_data['content'],
                        "latency_ms": model_data['latency_ms'],
                        "model_info": {
                            "id": model_data['model'],
                            "name": model_data['model'],
                            "provider": source_to_use.name if source_to_use else "unknown"
                        }
                    })
                
                assistant_msg = ChatMessage(
                    id=assistant_msg_id,
                    parent_id=message_id,
                    role="assistant",
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
                session_storage.save_session(session)
                
                # 记录每个模型的交互
                for model_data in parallel_models_data:
                    model_name = model_data['model_info']['name']
                    # 使用保存的消息历史（调用 API 时的消息）
                    model_messages = model_messages_map.get(model_name, [])
                    log_model_interaction(
                        session_id=session_id,
                        model=model_name,
                        messages=model_messages,
                        response=model_data['content'],
                        elapsed_time=model_data['latency_ms'] / 1000.0,
                        config=config_info
                    )
                
                logger.info(f"多模型回复完成并保存，共 {len(assistant_messages)} 个模型")
                
                yield f"data: {json.dumps({'type': 'done', 'model_count': len(assistant_messages)}, ensure_ascii=False)}\n\n"
                
            else:
                # 单模型模式
                model_to_use = models_to_use[0]
                start_time = time.time()
                
                # 为当前模型构建专属的消息历史
                model_messages = build_messages_for_model_regenerate(model_to_use)
                logger.info(f"🔧 重新生成 - 模型 {model_to_use} 的消息历史: {len(model_messages)} 条")
                
                client = OpenAI(
                    api_key=source_to_use.api_key,
                    base_url=source_to_use.base_url
                )
                
                stream = client.chat.completions.create(
                    model=model_to_use,
                    messages=model_messages,
                    temperature=session_config.temperature if session_config else 0.7,
                    top_p=session_config.top_p if session_config else 1.0,
                    stream=True,
                    **get_chat_completion_extra_params(source_to_use, model_to_use)
                )
                
                assistant_message = ''
                chunk_count = 0
                
                for chunk in stream:
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
                    content=assistant_message,
                    type="text",
                    created_at=assistant_msg_time,
                    children_ids=[],
                    model_info={
                        "id": model_to_use,
                        "name": model_to_use,
                        "provider": source_to_use.name if source_to_use else "unknown"
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
                
                session_storage.save_session(session)
                
                logger.info(f"AI 回复完成并保存，总长度: {len(assistant_message)}")
                
                done_data = {'type': 'done', 'message_id': assistant_msg_id}
                yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"重新生成失败: {e}", exc_info=True)
            # 记录错误
            if 'models_to_use' in locals() and 'api_messages' in locals():
                for model in models_to_use:
                    log_error(
                        session_id=session_id,
                        model=model,
                        messages=api_messages,
                        error=e,
                        stage="regenerate"
                    )
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
