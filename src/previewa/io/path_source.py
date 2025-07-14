import os
from pathlib import Path
from typing import List, Optional, Any
import pyperclip
from loguru import logger

class PathSource:
    """
    路径来源处理类，负责从不同来源获取文件路径
    """
    
    def __init__(self, source_type: str = "cli", source_data: Any = None):
        """
        初始化路径来源
        
        参数:
            source_type: 来源类型，可以是 "cli"(命令行)、"clipboard"(剪贴板)、"file"(文件)
            source_data: 来源数据，根据source_type有不同含义
                - cli: 路径字符串
                - clipboard: 无意义，可为None
                - file: 文本文件路径
        """
        self.source_type = source_type
        self.source_data = source_data
    
    def get_paths(self) -> List[str]:
        """
        根据来源类型获取路径列表
        
        返回:
            文件路径列表
        """
        if self.source_type == "cli":
            return self._get_paths_from_cli()
        elif self.source_type == "clipboard":
            return self._get_paths_from_clipboard()
        elif self.source_type == "file":
            return self._get_paths_from_file()
        else:
            logger.error(f"不支持的来源类型: {self.source_type}")
            return []
    
    def _get_paths_from_cli(self) -> List[str]:
        """从命令行参数获取路径"""
        path = self.source_data
        if not path:
            logger.warning("未提供路径")
            return []
        
        path = str(path).strip('"').strip("'")
        if not os.path.exists(path):
            logger.error(f"路径不存在: {path}")
            return []
        
        if os.path.isdir(path):
            # 如果是目录，获取目录下的所有文件
            result = []
            for root, _, files in os.walk(path):
                for file in files:
                    if file.startswith('.'):  # 忽略隐藏文件
                        continue
                    result.append(os.path.join(root, file))
            return result
        else:
            # 如果是单个文件，直接返回
            return [path]
    
    def _get_paths_from_clipboard(self) -> List[str]:
        """从剪贴板获取路径"""
        try:
            clipboard_content = pyperclip.paste().strip()
            if not clipboard_content:
                logger.warning("剪贴板内容为空")
                return []
            
            path = clipboard_content.strip('"').strip("'")
            if not os.path.exists(path):
                logger.error(f"剪贴板中的路径不存在: {path}")
                return []
            
            if os.path.isdir(path):
                # 如果是目录，获取目录下的所有文件
                result = []
                for root, _, files in os.walk(path):
                    for file in files:
                        if file.startswith('.'):  # 忽略隐藏文件
                            continue
                        result.append(os.path.join(root, file))
                return result
            else:
                # 如果是单个文件，直接返回
                return [path]
        except Exception as e:
            logger.error(f"读取剪贴板时出错: {e}")
            return []
    
    def _get_paths_from_file(self) -> List[str]:
        """从文本文件获取路径列表"""
        if not self.source_data:
            logger.warning("未提供文件路径")
            return []
        
        file_path = self.source_data
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                paths = [line.strip() for line in f if line.strip()]
            
            # 验证路径存在性
            valid_paths = []
            for path in paths:
                path = path.strip('"').strip("'")
                # 支持 http/https/ftp 等 URL 路径
                if path.startswith(('http://', 'https://', 'ftp://')):
                    valid_paths.append(path)
                elif os.path.exists(path):
                    valid_paths.append(path)
                else:
                    logger.warning(f"路径不存在: {path}")
            return valid_paths
        except Exception as e:
            logger.error(f"读取文件时出错: {e}")
            return []