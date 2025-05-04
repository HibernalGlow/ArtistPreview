from abc import ABC, abstractmethod
from typing import List, Dict, Any

class ClassificationMode(ABC):
    """分类模式基类"""
    
    def __init__(self, classifier):
        self.classifier = classifier
    
    @abstractmethod
    def process(self, paths: List[str], **kwargs) -> Dict[str, Any]:
        """
        处理路径列表并返回结果
        
        参数:
            paths: 文件路径列表
            **kwargs: 额外参数
            
        返回:
            包含处理结果的字典
        """
        pass

from .standard import StandardMode
from .intermediate import IntermediateMode
from .text_mode import TextMode

__all__ = ["ClassificationMode", "StandardMode", "IntermediateMode", "TextMode"]