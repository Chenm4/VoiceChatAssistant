"""
ID 生成工具

提供唯一 ID 生成功能，用于会话和消息标识。
生成的 ID 包含时间戳和随机字符，确保唯一性。
"""

import random
import string
from datetime import datetime


def generate_session_id() -> str:
    """
    生成会话 ID
    
    生成格式: YYYY-MM-DD_HH-MM-SS-mmm-xxxx
    其中 mmm 是毫秒，xxxx 是 4 位随机字符（小写字母+数字）
    
    Returns:
        str: 会话 ID，例如 "2026-01-31_23-45-12-345-a1b2"
        
    Example:
        >>> session_id = generate_session_id()
        >>> print(session_id)
        2026-01-31_23-45-12-345-a1b2
    """
    # 获取当前时间（精确到毫秒）
    now = datetime.now()
    
    # 格式化日期时间部分: 2026-01-30_10-32-12
    datetime_part = now.strftime("%Y-%m-%d_%H-%M-%S")
    
    # 获取毫秒（前3位）
    millisecond = now.strftime("%f")[:3]
    
    # 生成4位随机字符（小写字母+数字）
    random_chars = ''.join(
        random.choices(string.ascii_lowercase + string.digits, k=4)
    )
    
    # 组合完整 ID
    session_id = f"{datetime_part}-{millisecond}-{random_chars}"
    
    return session_id


def generate_message_id() -> str:
    """
    生成消息 ID
    
    格式与 session_id 相同，用于标识单条消息。
    
    Returns:
        str: 消息 ID
        
    Example:
        >>> message_id = generate_message_id()
        >>> print(message_id)
        2026-01-31_23-45-12-678-c3d4
    """
    return generate_session_id()


def main() -> None:
    """主函数：测试 ID 生成功能"""
    from backend.utils.logger import get_app_logger
    
    logger = get_app_logger()
    logger.info("测试 ID 生成:")
    
    for i in range(5):
        session_id = generate_session_id()
        logger.info(f"  {i+1}. {session_id}")


if __name__ == "__main__":
    main()
