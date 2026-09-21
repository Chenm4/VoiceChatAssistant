"""
会话持久化服务
将会话数据按月分组存储到本地 JSON 文件
索引与内容分离，优化加载性能
"""

import json
import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from backend.api.models import Session, SessionIndex, SessionIndexList
from backend.utils.logger import get_api_logger

logger = get_api_logger()


class SessionStorage:
    """
    会话存储服务
    
    存储架构：
    - data/sessions_index.json: 轻量级索引文件
    - data/storage/YYYY/MM/session_id.json: 按月分组的会话文件
    """
    
    def __init__(self, base_dir: str = "data"):
        """
        初始化会话存储
        
        Args:
            base_dir: 数据根目录
        """
        self.base_dir = Path(base_dir)
        self.index_file = self.base_dir / "sessions_index.json"
        self.storage_dir = self.base_dir / "storage"
        
        # 确保目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"会话存储初始化: base={self.base_dir}")
    
    def _get_session_path(self, session_id: str, created_at: Optional[int] = None) -> Path:
        """
        获取会话文件路径（按月分组）
        
        Args:
            session_id: 会话 ID
            created_at: 创建时间戳（如果为 None，从索引中查找）
        
        Returns:
            Path: 会话文件路径
        """
        if not created_at:
            # 从索引中查找创建时间
            index = self.load_index()
            for s in index.sessions:
                if s.id == session_id:
                    created_at = s.created_at
                    break
            
            if not created_at:
                # 如果索引中也没有，使用当前时间
                created_at = int(datetime.now().timestamp())
        
        # 按月分组: YYYY/MM/session_id.json
        dt = datetime.fromtimestamp(created_at)
        year_month_dir = self.storage_dir / str(dt.year) / f"{dt.month:02d}"
        year_month_dir.mkdir(parents=True, exist_ok=True)
        
        return year_month_dir / f"{session_id}.json"
    
    def _get_storage_path_str(self, session_id: str, created_at: int) -> str:
        """
        获取相对存储路径字符串（用于索引）
        
        Returns:
            str: 如 "2026/01/session_id.json"
        """
        dt = datetime.fromtimestamp(created_at)
        return f"{dt.year}/{dt.month:02d}/{session_id}.json"
    
    def load_index(self) -> SessionIndexList:
        """
        加载会话索引（轻量级，不包含消息内容）
        
        Returns:
            SessionIndexList: 会话索引列表
        """
        if not self.index_file.exists():
            logger.info("索引文件不存在，返回空列表")
            return SessionIndexList(sessions=[], current_session_id=None)
        
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return SessionIndexList(**data)
        except Exception as e:
            logger.error(f"加载索引失败: {e}", exc_info=True)
            return SessionIndexList(sessions=[], current_session_id=None)
    
    def save_index(self, index_list: SessionIndexList) -> bool:
        """
        保存会话索引
        
        Args:
            index_list: 会话索引列表
        
        Returns:
            bool: 是否成功
        """
        try:
            # 先写入临时文件，再重命名（原子操作）
            temp_path = self.index_file.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(index_list.dict(), f, ensure_ascii=False, indent=2)
            
            temp_path.replace(self.index_file)
            logger.debug(f"索引保存成功: {len(index_list.sessions)} 个会话")
            return True
        except Exception as e:
            logger.error(f"保存索引失败: {e}", exc_info=True)
            return False
    
    def load_session(self, session_id: str) -> Optional[Session]:
        """
        加载指定会话的完整内容
        
        Args:
            session_id: 会话 ID
        
        Returns:
            Optional[Session]: 会话对象，不存在则返回 None
        """
        try:
            session_path = self._get_session_path(session_id)
            
            if not session_path.exists():
                logger.warning(f"会话文件不存在: {session_id}")
                return None
            
            with open(session_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return Session(**data)
        except Exception as e:
            logger.error(f"加载会话失败: {session_id}, {e}", exc_info=True)
            return None
    
    def save_session(self, session: Session) -> bool:
        """
        保存会话（同时更新索引）
        
        Args:
            session: 会话对象
        
        Returns:
            bool: 是否成功
        """
        try:
            # 1. 保存会话文件
            session_path = self._get_session_path(session.id, session.created_at)
            session.storage_path = self._get_storage_path_str(session.id, session.created_at)
            
            # 先写入临时文件
            temp_path = session_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(session.dict(), f, ensure_ascii=False, indent=2)
            
            temp_path.replace(session_path)
            
            # 2. 更新索引
            index = self.load_index()
            
            # 统计使用的模型
            used_models = set()
            for msg in session.messages:
                if msg.model_info:
                    # 安全获取model_id，兼容字典和对象
                    if isinstance(msg.model_info, dict):
                        model_id = msg.model_info.get('id')
                    else:
                        model_id = msg.model_info.id
                    
                    if model_id:
                        used_models.add(model_id)
            
            # 创建或更新索引项
            session_index = SessionIndex(
                id=session.id,
                title=session.title,
                created_at=session.created_at,
                updated_at=session.updated_at,
                storage_path=session.storage_path,
                message_count=len(session.messages),
                audio_count=len(session.audio_files),
                used_models=list(used_models)
            )
            
            # 更新或添加到索引
            found = False
            for i, s in enumerate(index.sessions):
                if s.id == session.id:
                    index.sessions[i] = session_index
                    found = True
                    break
            
            if not found:
                index.sessions.append(session_index)
            
            # 保存索引
            self.save_index(index)
            
            logger.debug(f"会话保存成功: {session.id}")
            return True
            
        except Exception as e:
            logger.error(f"保存会话失败: {session.id}, {e}", exc_info=True)
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """
        删除会话（删除文件和索引）
        
        Args:
            session_id: 会话 ID
        
        Returns:
            bool: 是否成功
        """
        try:
            # 1. 删除会话文件
            session_path = self._get_session_path(session_id)
            if session_path.exists():
                session_path.unlink()
                logger.info(f"删除会话文件: {session_path}")
            
            # 2. 从索引中移除
            index = self.load_index()
            index.sessions = [s for s in index.sessions if s.id != session_id]
            self.save_index(index)
            
            logger.info(f"会话删除成功: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除会话失败: {session_id}, {e}", exc_info=True)
            return False
    
    def set_current_session(self, session_id: str) -> bool:
        """
        设置当前活动会话
        
        Args:
            session_id: 会话 ID
        
        Returns:
            bool: 是否成功
        """
        try:
            index = self.load_index()
            index.current_session_id = session_id
            return self.save_index(index)
        except Exception as e:
            logger.error(f"设置当前会话失败: {session_id}, {e}", exc_info=True)
            return False
    
    def backup_all(self) -> bool:
        """
        备份所有会话数据
        
        Returns:
            bool: 是否成功
        """
        try:
            from datetime import datetime
            import shutil
            
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_dir = self.base_dir / backup_name
            
            # 复制整个 data 目录
            shutil.copytree(self.base_dir, backup_dir)
            
            logger.info(f"备份成功: {backup_dir}")
            return True
        except Exception as e:
            logger.error(f"备份失败: {e}", exc_info=True)
            return False


# 全局存储实例
session_storage = SessionStorage()
