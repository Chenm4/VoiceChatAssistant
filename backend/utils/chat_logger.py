"""
聊天消息日志记录工具

专门记录发送给模型的消息和接收到的响应。
按会话分文件存储，清晰展示每个模型的请求和响应。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


# 常量定义
CHAT_LOGS_DIR = Path(__file__).parent.parent.parent / "logs" / "chat_history"


class SessionChatLogger:
    """会话聊天日志记录器
    
    为每个会话创建独立的日志文件，按时间线记录模型交互。
    """
    
    def __init__(self, session_id: str):
        """初始化会话日志记录器
        
        Args:
            session_id: 会话ID
        """
        self.session_id = session_id
        self.log_file = self._create_log_file()
        
    def _create_log_file(self) -> Path:
        """创建日志文件
        
        Returns:
            Path: 日志文件路径
        """
        # 创建日志目录
        CHAT_LOGS_DIR.mkdir(parents=True, exist_ok=True)
        
        # 生成日志文件名: session_{session_id}_{date}.log
        date_str = datetime.now().strftime('%Y%m%d')
        log_file = CHAT_LOGS_DIR / f"session_{self.session_id}_{date_str}.log"
        
        # 如果是新文件，写入会话头部
        if not log_file.exists():
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write("=" * 100 + "\n")
                f.write(f"会话日志 - Session ID: {self.session_id}\n")
                f.write(f"创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 100 + "\n\n")
        
        return log_file
    
    def _write(self, content: str):
        """写入日志内容
        
        Args:
            content: 日志内容
        """
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(content)
    
    def _truncate_text(self, text: str, max_length: int = 10) -> str:
        """截断文本到指定长度
        
        Args:
            text: 原始文本
            max_length: 最大长度
            
        Returns:
            str: 截断后的文本
        """
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
    
    def log_model_interaction(
        self,
        model: str,
        messages: List[Dict[str, str]],
        response: str,
        elapsed_time: float,
        config: Dict[str, Any] = None
    ):
        """记录单个模型的完整交互（请求+响应）
        
        Args:
            model: 模型名称
            messages: 发送给模型的消息列表
            response: 模型响应内容
            elapsed_time: 响应耗时（秒）
            config: 配置信息
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 构建日志内容
        log_content = []
        log_content.append("\n" + "─" * 100)
        log_content.append(f"⏰ 时间: {timestamp}")
        log_content.append(f"🤖 模型: {model}")
        log_content.append(f"⏱️  耗时: {elapsed_time:.2f}秒")
        
        if config:
            config_str = ", ".join([f"{k}={v}" for k, v in config.items()])
            log_content.append(f"⚙️  配置: {config_str}")
        
        log_content.append("")
        log_content.append(f"📤 发送消息 (共{len(messages)}条):")
        
        # 显示发送的消息摘要
        for idx, msg in enumerate(messages, 1):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            preview = self._truncate_text(content, 10)
            log_content.append(f"   {idx}. [{role}] {preview}")
        
        log_content.append("")
        log_content.append(f"📥 模型响应:")
        response_preview = self._truncate_text(response, 10)
        log_content.append(f"   {response_preview}")
        log_content.append(f"   (完整长度: {len(response)} 字符)")
        
        # 写入日志
        self._write("\n".join(log_content) + "\n")
    
    def log_error(
        self,
        model: str,
        messages: List[Dict[str, str]],
        error: Exception,
        stage: str = "unknown"
    ):
        """记录错误
        
        Args:
            model: 模型名称
            messages: 发送的消息列表
            error: 错误对象
            stage: 错误阶段
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        log_content = []
        log_content.append("\n" + "─" * 100)
        log_content.append(f"⏰ 时间: {timestamp}")
        log_content.append(f"❌ 错误 - 模型: {model}")
        log_content.append(f"阶段: {stage}")
        log_content.append(f"错误类型: {type(error).__name__}")
        log_content.append(f"错误信息: {str(error)}")
        
        log_content.append("")
        log_content.append(f"📤 发送消息 (共{len(messages)}条):")
        for idx, msg in enumerate(messages, 1):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            preview = self._truncate_text(content, 10)
            log_content.append(f"   {idx}. [{role}] {preview}")
        
        self._write("\n".join(log_content) + "\n")


# 全局会话日志记录器缓存
_session_loggers: Dict[str, SessionChatLogger] = {}


def get_session_logger(session_id: str) -> SessionChatLogger:
    """获取或创建会话日志记录器
    
    Args:
        session_id: 会话ID
        
    Returns:
        SessionChatLogger: 会话日志记录器
    """
    if session_id not in _session_loggers:
        _session_loggers[session_id] = SessionChatLogger(session_id)
    return _session_loggers[session_id]


def log_model_interaction(
    session_id: str,
    model: str,
    messages: List[Dict[str, str]],
    response: str,
    elapsed_time: float,
    config: Dict[str, Any] = None
):
    """记录模型交互（便捷函数）
    
    Args:
        session_id: 会话ID
        model: 模型名称
        messages: 发送的消息列表
        response: 模型响应
        elapsed_time: 耗时（秒）
        config: 配置信息
    """
    logger = get_session_logger(session_id)
    logger.log_model_interaction(model, messages, response, elapsed_time, config)


def log_error(
    session_id: str,
    model: str,
    messages: List[Dict[str, str]],
    error: Exception,
    stage: str = "unknown"
):
    """记录错误（便捷函数）
    
    Args:
        session_id: 会话ID
        model: 模型名称
        messages: 发送的消息列表
        error: 错误对象
        stage: 错误阶段
    """
    logger = get_session_logger(session_id)
    logger.log_error(model, messages, error, stage)
