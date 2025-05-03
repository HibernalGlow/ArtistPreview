import os
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger

from . import ClassificationMode

class TextMode(ClassificationMode):
    """
    文本模式 - 从文本文件读取路径，生成分类结果YAML文件
    """
    
    def __init__(self, classifier):
        super().__init__(classifier)
        
    def process(self, paths: List[str], **kwargs) -> Dict[str, Any]:
        """
        处理文件路径列表，生成分类结果
        
        参数:
            paths: 文件路径列表，一般是从文本文件中读取的
            **kwargs: 额外参数，可能包括:
                - output_file: 输出的YAML文件路径
        
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
        
        # 分类文件
        classification = self.classifier.classify_files(paths)
        
        # 记录结果
        results = {
            "total_files": len(paths),
            "classified": 0,
            "unclassified": 0,
            "artist_stats": {},
            "classification": classification  # 保存完整分类结果
        }
        
        # 统计信息
        for artist, files in classification.items():
            if artist == "未识别":
                results["unclassified"] = len(files)
                logger.warning(f"有 {len(files)} 个文件未能识别对应画师")
            else:
                results["classified"] += len(files)
                results["artist_stats"][artist] = len(files)
                logger.info(f"画师 [{artist}]: 识别了 {len(files)} 个文件")
        
        logger.info(f"总计: 识别了 {results['classified']} 个文件, 未识别 {results['unclassified']} 个文件")
        
        # 保存到YAML文件
        output_file = kwargs.get("output_file")
        if output_file:
            self._save_to_yaml(results, output_file)
        
        return results
    
    def _save_to_yaml(self, results: Dict, output_file: str) -> None:
        """
        将结果保存到YAML文件
        
        参数:
            results: 处理结果字典
            output_file: 输出文件路径
        """
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump(results, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"分类结果已保存至: {output_file}")
        except Exception as e:
            logger.error(f"保存分类结果时出错: {e}")
    
    @staticmethod
    def read_paths_from_file(file_path: str) -> List[str]:
        """
        从文本文件中读取路径列表
        
        参数:
            file_path: 文本文件路径
            
        返回:
            文件路径列表
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                paths = [line.strip() for line in f if line.strip()]
            return paths
        except Exception as e:
            logger.error(f"读取文件路径时出错: {e}")
            return []