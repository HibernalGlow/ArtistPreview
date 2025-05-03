import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from loguru import logger

from .artist_db import ArtistDatabase

class ArtistClassifier:
    """
    画师分类器核心类，负责识别文件对应的画师并进行分类操作
    """
    
    def __init__(self, artist_db=None):
        """
        初始化分类器
        
        参数:
            artist_db: 画师数据库实例，如不提供则创建新实例
        """
        self.artist_db = artist_db or ArtistDatabase()
        
        # 分类器的基本状态
        self.pending_dir = None  # 待处理的目录
        
    def update_artist_list(self) -> Dict[str, str]:
        """
        更新画师列表
        
        返回:
            更新后的画师匹配模式字典
        """
        return self.artist_db.update()
    
    def identify_artist(self, filepath: str) -> Optional[str]:
        """
        识别文件对应的画师
        
        参数:
            filepath: 文件路径
            
        返回:
            画师名称，如未匹配则返回None
        """
        filename = os.path.basename(filepath)
        return self.artist_db.find_artist(filename)
    
    def classify_file(self, filepath: str) -> Tuple[str, Optional[str]]:
        """
        对单个文件进行分类
        
        参数:
            filepath: 文件路径
            
        返回:
            (文件路径, 识别的画师)
        """
        artist = self.identify_artist(filepath)
        return filepath, artist
    
    def classify_files(self, filepaths: List[str]) -> Dict[str, List[str]]:
        """
        批量分类多个文件
        
        参数:
            filepaths: 文件路径列表
            
        返回:
            {画师名: [文件路径列表]}，未识别的文件会放在键为"未识别"的列表中
        """
        result = {}
        
        for filepath in filepaths:
            _, artist = self.classify_file(filepath)
            
            if artist:
                if artist not in result:
                    result[artist] = []
                result[artist].append(filepath)
            else:
                if "未识别" not in result:
                    result["未识别"] = []
                result["未识别"].append(filepath)
                
        return result
    
    def set_pending_dir(self, dir_path: str) -> None:
        """
        设置待处理目录
        
        参数:
            dir_path: 目录路径
            
        异常:
            ValueError: 当路径不存在或不是目录时抛出
        """
        path = Path(dir_path)
        if not path.exists():
            raise ValueError(f"路径不存在: {dir_path}")
        if not path.is_dir():
            raise ValueError(f"路径不是目录: {dir_path}")
            
        self.pending_dir = str(path)
        logger.info(f"已设置待处理目录: {self.pending_dir}")
    
    def get_pending_files(self) -> List[str]:
        """
        获取待处理目录中的所有文件
        
        返回:
            文件路径列表
        """
        if not self.pending_dir:
            logger.warning("未设置待处理目录")
            return []
            
        result = []
        for root, _, files in os.walk(self.pending_dir):
            for file in files:
                if file.startswith('.'):  # 忽略隐藏文件
                    continue
                result.append(os.path.join(root, file))
        
        return result