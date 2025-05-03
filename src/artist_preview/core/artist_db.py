import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

class ArtistDatabase:
    """
    画师数据库管理类，处理画师列表的加载、更新和匹配
    """
    
    def __init__(self, cache_path: Optional[str] = None):
        # 设置缓存文件路径
        if cache_path:
            self.cache_path = Path(cache_path)
        else:
            # 默认使用原项目中的缓存路径
            self.cache_path = Path(__file__).parents[3] / "scripts" / "artist_cache.json"
        
        self.patterns = {}
        self.load_artist_list()
    
    def load_artist_list(self) -> Dict[str, str]:
        """
        加载画师列表
        
        返回:
            画师模式匹配字典 {pattern: artist_name}
        """
        try:
            if self.cache_path.exists():
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    self.patterns = json.load(f)
                logger.info(f"从 {self.cache_path} 加载了 {len(self.patterns)} 个画师")
            else:
                logger.warning(f"未找到画师缓存文件: {self.cache_path}, 将使用空列表")
                self.patterns = {}
                
            return self.patterns
        except Exception as e:
            logger.error(f"加载画师列表时出现错误: {e}")
            self.patterns = {}
            return {}
    
    def update(self) -> Dict[str, str]:
        """
        更新画师列表
        
        返回:
            更新后的画师模式匹配字典
        """
        # 这里可以实现从外部源更新画师列表的逻辑
        # 在原代码中这部分功能是在ArtistClassifier中实现的
        # 此处作为示例，仅保存当前的模式列表
        
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.patterns, f, ensure_ascii=False, indent=4)
            logger.info(f"已更新画师列表, 保存于 {self.cache_path}")
        except Exception as e:
            logger.error(f"更新画师列表时出现错误: {e}")
            
        return self.patterns
    
    def get_patterns(self) -> Dict[str, str]:
        """获取画师匹配模式字典"""
        return self.patterns
    
    def add_pattern(self, pattern: str, artist_name: str) -> None:
        """添加画师匹配模式"""
        self.patterns[pattern] = artist_name
    
    def remove_pattern(self, pattern: str) -> bool:
        """移除画师匹配模式"""
        if pattern in self.patterns:
            del self.patterns[pattern]
            return True
        return False
    
    def find_artist(self, filename: str) -> Optional[str]:
        """
        根据文件名查找匹配的画师
        
        参数:
            filename: 文件名
            
        返回:
            匹配的画师名称，如果未匹配则返回None
        """
        for pattern, artist in self.patterns.items():
            if re.search(pattern, filename, re.IGNORECASE):
                return artist
        return None