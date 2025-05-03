import os
import shutil
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

from . import ClassificationMode

class IntermediateMode(ClassificationMode):
    """
    中间分类模式 - 将文件移动到中间目录，可选是否创建画师子文件夹
    """
    
    def __init__(self, classifier, create_folders=False):
        super().__init__(classifier)
        self.create_folders = create_folders
        
    def process(self, paths: List[str], **kwargs) -> Dict[str, Any]:
        """
        处理文件列表，按中间模式分类文件
        
        参数:
            paths: 文件路径列表
            **kwargs: 额外参数，可能包括:
                - output_dir: 中间输出目录
                - create_folders: 是否创建画师文件夹（优先级高于构造函数）
        
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
        
        # 获取基础目录和参数
        base_dir = kwargs.get("output_dir")
        if not base_dir:
            parent_dir = os.path.dirname(paths[0])
            base_dir = os.path.join(parent_dir, "分类结果")
        
        # 可以通过kwargs覆盖构造函数的设置
        create_folders = kwargs.get("create_folders", self.create_folders)
        
        logger.info(f"中间输出目录: {base_dir}, 创建画师文件夹: {create_folders}")
        os.makedirs(base_dir, exist_ok=True)
        
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
            
            # 确定目标目录    
            if create_folders:
                artist_dir = os.path.join(base_dir, artist)
                os.makedirs(artist_dir, exist_ok=True)
            else:
                artist_dir = base_dir
            
            # 移动文件
            for file_path in files:
                file_name = os.path.basename(file_path)
                
                # 如果不创建画师文件夹，则在文件名前添加画师名称
                if not create_folders:
                    file_name = f"{artist}_{file_name}"
                
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