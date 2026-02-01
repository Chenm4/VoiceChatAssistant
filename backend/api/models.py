"""
API 数据模型
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import time


class ConfigSource(BaseModel):
    """单个 API 配置源"""
    name: str
    api_key: str
    models: List[str]
    base_url: str


class ConfigList(BaseModel):
    """所有配置源列表"""
    sources: List[ConfigSource]
    current_source: str  # 当前选中的配置源名称
    current_model: str   # 当前选中的模型


class ConfigModel(BaseModel):
    """API 配置模型（向后兼容）"""
    api_key: Optional[str] = ""
    model: str = "gpt-3.5-turbo"
    base_url: str = "https://api.openai.com/v1"


class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    name: str
    provider: str = "unknown"  # 默认值，防止旧数据中为 None


class TokenUsage(BaseModel):
    """Token 使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatMessage(BaseModel):
    """
    聊天消息模型 - 树形结构
    支持多分支对话和并行响应
    """
    id: str  # 消息唯一标识 (UUID)
    parent_id: Optional[str] = None  # 父消息 ID
    role: str  # 'user', 'assistant', or 'system'
    content: str
    type: str = "text"  # 消息类型: text, image, etc.
    created_at: int = Field(default_factory=lambda: int(time.time()))
    children_ids: List[str] = Field(default_factory=list)  # 子消息 ID 列表
    
    # Assistant 消息专有字段
    model_info: Optional[ModelInfo] = None
    usage: Optional[TokenUsage] = None
    status: Optional[str] = None  # success, error, pending
    latency_ms: Optional[int] = None  # 响应延迟(毫秒)
    is_parallel_response: Optional[bool] = None  # 是否为并行响应
    parallel_group_id: Optional[str] = None  # 并行响应组ID，相同ID的消息应横向显示
    parallel_models: Optional[List[Dict]] = None  # 多模型并行时的所有模型响应


class SessionConfig(BaseModel):
    """会话配置"""
    source_name: Optional[str] = None
    models: List[str] = Field(default_factory=list)
    temperature: float = 0.7
    top_p: float = 1.0
    system_prompt: Optional[str] = None


class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str
    parent_id: Optional[str] = None  # 从哪条消息继续对话


class ChatResponse(BaseModel):
    """聊天响应模型"""
    success: bool
    message: Optional[str] = None


class RecordingResponse(BaseModel):
    """录音响应模型"""
    success: bool
    message: Optional[str] = None
    text: Optional[str] = None


class Session(BaseModel):
    """
    会话模型 - 支持树形消息结构和动态 system prompt
    """
    id: str
    title: str
    created_at: int  # Unix 时间戳
    updated_at: int  # Unix 时间戳
    system_prompt: Optional[str] = None  # 全局系统提示词
    messages: List[ChatMessage] = Field(default_factory=list)
    session_config: Optional[SessionConfig] = None
    storage_path: Optional[str] = None  # 存储路径


class SessionIndex(BaseModel):
    """会话索引（轻量级，用于列表显示）"""
    id: str
    title: str
    created_at: int
    updated_at: int
    storage_path: str
    message_count: int = 0
    used_models: List[str] = Field(default_factory=list)  # 该会话使用过的模型列表


class SessionIndexList(BaseModel):
    """会话索引列表"""
    sessions: List[SessionIndex]
    current_session_id: Optional[str] = None


class SessionList(BaseModel):
    """会话列表模型（包含完整消息）"""
    sessions: List[Session]
    current_session_id: Optional[str] = None


class MessageUpdateRequest(BaseModel):
    """消息更新请求"""
    content: str


class BatchDeleteRequest(BaseModel):
    """批量删除消息请求"""
    message_indices: List[int]  # 要删除的消息索引列表


class RegenerateMessageRequest(BaseModel):
    """重新生成消息请求"""
    message_id: str  # 要替换的消息ID
    new_content: str  # 新的消息内容
    model: Optional[str] = None  # 可选：指定使用的模型
