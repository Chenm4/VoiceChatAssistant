"""
API 数据模型
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Literal
import time


DEFAULT_SCREENSHOT_PROMPT = (
    "请识别截图中的笔试题。回答时请在开头先简要、直接地给出最终答案，"
    "然后再逐题说明简要思路；代码题请给出可运行代码并分析时间复杂度和空间复杂度。"
)


class ConfigSource(BaseModel):
    """单个 API 配置源"""
    name: str
    api_key: str
    models: List[str]
    base_url: str

    @validator("api_key")
    def api_key_must_be_ascii(cls, value: str) -> str:
        """HTTP Authorization headers cannot contain non-ASCII API keys."""
        if value and not value.isascii():
            raise ValueError("API Key 只能包含 ASCII 字符，请检查是否误粘贴了中文内容")
        return value


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
    reasoning_effort: Optional[str] = None


class TokenUsage(BaseModel):
    """Token 使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class MessageAttachment(BaseModel):
    """A locally stored attachment associated with a chat message."""
    id: str
    type: Literal["image"] = "image"
    mime_type: str
    filename: str
    width: Optional[int] = None
    height: Optional[int] = None
    size: int = 0


class ModelTarget(BaseModel):
    """One model together with the API configuration source that serves it."""
    source_name: str
    model: str
    # Keep the setting on the target because one session can call models from
    # several providers at the same time.
    reasoning_effort: Literal[
        "none", "minimal", "low", "medium", "high", "xhigh"
    ] = "none"


class ChatMessage(BaseModel):
    """
    聊天消息模型 - 树形结构
    支持多分支对话和并行响应
    """
    model_config = {"protected_namespaces": ()}
    id: str  # 消息唯一标识 (UUID)
    parent_id: Optional[str] = None  # 父消息 ID
    role: str  # 'user', 'assistant', or 'system'
    content: str
    type: str = "text"  # 消息类型: text, image, etc.
    attachments: List[MessageAttachment] = Field(default_factory=list)
    created_at: int = Field(default_factory=lambda: int(time.time()))
    children_ids: List[str] = Field(default_factory=list)  # 子消息 ID 列表
    
    scene_name: Optional[str] = None
    answer_versions: List[Dict] = Field(default_factory=list)

    # Assistant 消息专有字段
    model_info: Optional[ModelInfo] = None
    usage: Optional[TokenUsage] = None
    status: Optional[str] = None  # success, error, pending
    latency_ms: Optional[int] = None  # 响应延迟(毫秒)
    is_parallel_response: Optional[bool] = None  # 是否为并行响应
    parallel_group_id: Optional[str] = None  # 并行响应组ID，相同ID的消息应横向显示
    parallel_models: Optional[List[Dict]] = None  # 多模型并行时的所有模型响应


class PromptScene(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=200)
    rules: str = Field(default="", max_length=30000)
    background: str = Field(default="", max_length=100000)


class SceneCatalog(BaseModel):
    common_rules: str = Field(default="回答简洁、口语化，先说重点。涉及项目经历时依据提供的资料，不编造事实。", max_length=30000)
    scenes: List[PromptScene] = Field(default_factory=list, max_length=100)


class SessionConfig(BaseModel):
    """会话配置"""
    model_config = {"protected_namespaces": ()}
    active_scene: Optional[PromptScene] = None
    scene_common_rules: str = ""
    answer_highlight_enabled: bool = False
    source_name: Optional[str] = None
    models: List[str] = Field(default_factory=list)
    # New format: supports selecting models from multiple API sources.
    # source_name/models remain readable for existing saved sessions.
    model_targets: List[ModelTarget] = Field(default_factory=list)
    temperature: float = 0.7
    top_p: float = 1.0
    system_prompt: Optional[str] = None
    # 模板内容在创建/选择模板时保存为快照；之后不会按模板 ID 自动追新版本。
    prompt_template_id: Optional[str] = None
    prompt_template_version: Optional[int] = Field(default=None, ge=1)
    user_prompt_template: Optional[str] = None
    # None 是旧会话的兼容状态：既不读取共享背景，也不追加 background_context。
    background_mode: Optional[Literal["shared", "custom", "none"]] = None
    # 与行为规则分开保存的个人经历、实习和项目背景。
    background_context: Optional[str] = None
    # 上下文控制：None 表示使用 config.py 中的全局默认值。
    max_history_turns: Optional[int] = Field(default=None, ge=1, le=100)
    # 历史字段名保留兼容旧会话；数值现在按 tokenizer 的 token 数解释。
    max_history_chars: Optional[int] = Field(default=None, ge=1000, le=200000)
    include_assistant_history: Optional[bool] = None
    # 截图答题时使用的会话级基础指令；输入框文字会作为补充要求附加。
    screenshot_prompt: str = Field(
        default=DEFAULT_SCREENSHOT_PROMPT,
        min_length=1,
        max_length=4000,
    )
    # 当前会话的消息阅读样式。
    display_font_size: int = Field(default=16, ge=12, le=72)
    display_line_height: float = Field(default=1.7, ge=1.0, le=3.0)


class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str
    parent_id: Optional[str] = None  # 从哪条消息继续对话
    session_id: Optional[str] = None
    attachment_ids: List[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """聊天响应模型"""
    success: bool
    message: Optional[str] = None


class RecordingStartRequest(BaseModel):
    input_device_index: Optional[int] = Field(default=None, ge=0)
    input_device_name: Optional[str] = None


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
    # WAV filenames captured while this session was active, in recording order.
    audio_files: List[str] = Field(default_factory=list)
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
    audio_count: int = 0
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
    attachment_ids: Optional[List[str]] = None


class BatchDeleteRequest(BaseModel):
    """批量删除消息请求"""
    message_indices: List[int]  # 要删除的消息索引列表


class RegenerateMessageRequest(BaseModel):
    """重新生成消息请求"""
    preserve_answer: bool = False
    message_id: str  # 要替换的消息ID
    new_content: str  # 新的消息内容
    model: Optional[str] = None  # 可选：指定使用的模型
    reasoning_effort: Optional[Literal["none", "minimal", "low", "medium", "high", "xhigh"]] = None
    attachment_ids: Optional[List[str]] = None
