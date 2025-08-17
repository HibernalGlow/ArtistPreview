"""
配置管理模块
负责应用程序的配置设置
"""
from dataclasses import dataclass
from typing import List


@dataclass
class AppConfig:
    """应用程序配置类"""
    
    # 默认路径设置
    default_source_path: str = "E:\\1EHV"
    default_destination_path: str = "E:\\2EHV\\crash"
    default_auto_dir: str = "E:\\1EHV"
    
    # 默认相似度阈值
    default_similarity_threshold: float = 0.8
    
    # 输出文件设置
    output_filename: str = "output_paths.txt"
    pairs_json_filename: str = "folder_pairs.json"

    # 移动操作默认策略
    default_conflict_policy: str = "skip"  # skip | overwrite | rename
    default_move_direction: str = "source_to_target"  # source_to_target | target_to_source
    
    # 界面设置
    header_title: str = "文件夹相似度检测与批量移动工具"
    header_border_style: str = "green"
    
    # 进度条设置
    progress_description: str = "扫描文件夹..."
    
    # 颜色主题设置
    colors = {
        "info": "yellow",
        "success": "green", 
        "error": "red",
        "warning": "yellow",
        "accent": "cyan",
        "highlight": "bold cyan"
    }


class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.config = AppConfig()
    
    def get_config(self) -> AppConfig:
        """获取配置对象"""
        return self.config
    
    def update_default_paths(
        self, 
        source_path: str = None, 
        destination_path: str = None, 
        auto_dir: str = None
    ):
        """
        更新默认路径设置
        
        Args:
            source_path: 默认源路径
            destination_path: 默认目标路径  
            auto_dir: 默认自动获取目录
        """
        if source_path:
            self.config.default_source_path = source_path
        if destination_path:
            self.config.default_destination_path = destination_path
        if auto_dir:
            self.config.default_auto_dir = auto_dir
    
    def update_similarity_threshold(self, threshold: float):
        """
        更新默认相似度阈值
        
        Args:
            threshold: 相似度阈值 (0-1之间)
        """
        if 0 <= threshold <= 1:
            self.config.default_similarity_threshold = threshold
        else:
            raise ValueError("相似度阈值必须在0-1之间")
    
    def update_output_filename(self, filename: str):
        """
        更新输出文件名
        
        Args:
            filename: 输出文件名
        """
        self.config.output_filename = filename

    def update_pairs_json_filename(self, filename: str):
        self.config.pairs_json_filename = filename
