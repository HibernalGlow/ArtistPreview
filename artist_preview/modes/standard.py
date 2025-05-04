import os
import shutil
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

from . import ClassificationMode

class StandardMode(ClassificationMode):
    """
    标准分类模式 - 直接将文件移动到对应画师的目录中
    """
    
    def __init__(self, classifier):
        super().__init__(classifier)
        
    def process(self, paths: List[str], **kwargs) -> Dict[str, Any]:
        """
        处理文件列表，将文件分类到对应画师目录
        
        参数:
            paths: 文件路径列表
            **kwargs: 额外参数，可能包括:
                - output_dir: 输出基础目录
        
        返回:
            处理结果统计信息字典
        """
        if not paths:
            logger.warning("没有文件需要处理")
            return {
                "total_files": 0,
                "classified": 0,
                "unclassified": 0,
                "artist_stats": {}
            }
        
        # 获取基础目录，默认为第一个文件的父目录
        base_dir = kwargs.get("output_dir", os.path.dirname(paths[0]))
        logger.info(f"输出基础目录: {base_dir}")
        
        # 分类文件
        classification = self.classifier.classify_files(paths)
        
        # 记录结果
        results = {
            "total_files": len(paths),
            "classified": 0,
            "unclassified": 0,
            "artist_stats": {}
        }
        
        # 处理每个画师的文件
        for artist, files in classification.items():
            if artist == "未识别":
                results["unclassified"] = len(files)
                logger.warning(f"有 {len(files)} 个文件未能识别对应画师")
                continue
                
            # 创建目标目录
            artist_dir = os.path.join(base_dir, artist)
            os.makedirs(artist_dir, exist_ok=True)
            
            # 移动文件
            for file_path in files:
                file_name = os.path.basename(file_path)
                dest_path = os.path.join(artist_dir, file_name)
                
                try:
                    shutil.move(file_path, dest_path)
                    logger.debug(f"已移动: {file_path} -> {dest_path}")
                except Exception as e:
                    logger.error(f"移动文件时出错: {e}")
            
            results["classified"] += len(files)
            results["artist_stats"][artist] = len(files)
            logger.info(f"画师 [{artist}]: 处理了 {len(files)} 个文件")
            
        logger.info(f"总计: 处理了 {results['classified']} 个文件, 未分类 {results['unclassified']} 个文件")
        return results