# -*- coding: utf-8 -*-
"""
本地配置文件（包含敏感信息，已被 .gitignore 忽略，请勿提交）

请在下方填入您的 API Key 后重启服务生效。
也可以在 Web 界面的"设置"中直接编辑配置源。
"""

# ==================== OpenAI 兼容 API 配置（多配置源） ====================
OPENAI_CONFIG = [
    {
        "name": "OpenAI",
        "api_key": "",  # 填写您的 OpenAI API Key
        "models": ["gpt-4", "gpt-3.5-turbo"],
        "base_url": "https://api.openai.com/v1"
    },
    {
        "name": "DeepSeek",
        "api_key": "",  # 填写您的 DeepSeek API Key
        "models": ["deepseek-chat", "deepseek-coder"],
        "base_url": "https://api.deepseek.com/v1"
    },
    {
        "name": "通义千问",
        "api_key": "sk-0102c03bcebe4469a5bacedd09309ea6",  # 硬编码，临时使用
        "models": ["qwen-max", "qwen-plus"],
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
    },
    {
        "name": "本地模型",
        "api_key": "local",
        "models": ["qwen2.5:latest"],
        "base_url": "http://localhost:11434/v1"
    }
]

# 默认使用的配置源（必须是 OPENAI_CONFIG 中的一个 name）
DEFAULT_CONFIG_NAME = "通义千问"

# ==================== 字节跳动语音识别配置 ====================
# 注意：实时识别已改用火山引擎 v2/asr 协议（见下方 VOLCENGINE_CONFIG）。
# 此处为字节跳动开放平台 SAUC 协议凭据（app_key/access_key），
# 与火山引擎 appid/token 不同，需单独申请；留空时文件识别会自动降级到火山引擎。
BYTEDANCE_ASR_CONFIG = {
    "app_key": "",   # 您的 app_key
    "access_key": "",  # 您的 access_key
    "url": "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream",
    "segment_duration": 200,  # 每个音频包的时长（毫秒）
}

# ==================== 火山引擎配置（实时识别 + 文件识别备用） ====================
VOLCENGINE_CONFIG = {
    "appid": "2448163126",
    "token": "OYKhmgoizSmGsLJSdZ7WIMxZVbXTzfwH",
    "cluster": "volcengine_streaming_common",
    "ws_url": "wss://openspeech.bytedance.com/api/v2/asr",  # 实时流式识别 WebSocket 地址
    "segment_duration": 200,  # 每个音频包的时长（毫秒）
}

# ==================== 音频参数配置 ====================
AUDIO_CONFIG = {
    'rate': 16000,        # 采样率（Hz），火山引擎要求 16000
    'channels': 1,        # 声道数
    'chunk': 960,         # 每次读取的音频块大小
    'format': 8,          # pyaudio.paInt16
    'language': 'zh-CN',  # 识别语言
    'max_duration_minutes': 5,  # 最大录音时长（分钟）
}

# ==================== 快捷键配置 ====================
HOTKEY_CONFIG = {
    "toggle": "ctrl+8",       # 全局快捷键（需要辅助功能权限）
    "local_toggle": "ctrl+r", # 局部快捷键（前端页面中使用，无需权限）
}
