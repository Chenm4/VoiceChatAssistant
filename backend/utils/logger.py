"""
日志工具模块
提供统一的日志记录功能
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler

class Logger:
    """日志管理器"""
    
    _loggers = {}
    
    @staticmethod
    def get_logger(name: str, log_file: str = None, level=logging.INFO):
        """
        获取日志记录器
        
        Args:
            name: 日志记录器名称
            log_file: 日志文件路径（可选）
            level: 日志级别
            
        Returns:
            logging.Logger: 日志记录器实例
        """
        if name in Logger._loggers:
            return Logger._loggers[name]
        
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False
        
        # 清除已有的处理器
        logger.handlers.clear()
        
        # 日志格式
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 文件处理器（如果指定了文件）
        if log_file:
            # 确保日志目录存在
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 使用 RotatingFileHandler，自动轮转日志文件
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        Logger._loggers[name] = logger
        return logger
    
    @staticmethod
    def setup_app_logger(app_name: str = "chatgpt_web"):
        """
        设置应用日志记录器
        
        Args:
            app_name: 应用名称
            
        Returns:
            logging.Logger: 应用日志记录器
        """
        # 日志文件路径
        log_dir = Path(__file__).parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        # 使用日期作为日志文件名的一部分
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = log_dir / f'{app_name}_{today}.log'
        
        return Logger.get_logger(app_name, str(log_file))


# 预定义的日志记录器
def get_app_logger():
    """获取应用主日志记录器"""
    return Logger.setup_app_logger('chatgpt_web')


def get_asr_logger():
    """获取语音识别日志记录器"""
    log_dir = Path(__file__).parent.parent / 'logs'
    today = datetime.now().strftime('%Y-%m-%d')
    log_file = log_dir / f'asr_{today}.log'
    return Logger.get_logger('asr', str(log_file))


def get_api_logger():
    """获取 API 日志记录器"""
    log_dir = Path(__file__).parent.parent / 'logs'
    today = datetime.now().strftime('%Y-%m-%d')
    log_file = log_dir / f'api_{today}.log'
    return Logger.get_logger('api', str(log_file))


# 便捷函数
def log_info(message: str, logger_name: str = 'chatgpt_web'):
    """记录信息日志"""
    logger = Logger.get_logger(logger_name)
    logger.info(message)


def log_error(message: str, logger_name: str = 'chatgpt_web', exc_info=False):
    """记录错误日志"""
    logger = Logger.get_logger(logger_name)
    logger.error(message, exc_info=exc_info)


def log_warning(message: str, logger_name: str = 'chatgpt_web'):
    """记录警告日志"""
    logger = Logger.get_logger(logger_name)
    logger.warning(message)


def log_debug(message: str, logger_name: str = 'chatgpt_web'):
    """记录调试日志"""
    logger = Logger.get_logger(logger_name)
    logger.debug(message)
