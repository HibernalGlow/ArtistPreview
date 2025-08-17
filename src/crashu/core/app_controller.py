"""
应用程序主控制器
负责协调各个模块的工作流程
"""
import os
from .folder_manager import FolderManager
from .ui_manager import UIManager
from .output_manager import OutputManager
from .config import ConfigManager
from crashp import PairManager


class AppController:
    """应用程序控制器"""

    def __init__(self):
        # 初始化各子管理器
        self.config_manager = ConfigManager()
        self.folder_manager = FolderManager()
        self.ui_manager = UIManager()
        self.output_manager = OutputManager()
        self.pair_manager = PairManager()
    
    def run(self):
        """运行主程序"""
        # 显示程序头部
        self.ui_manager.show_header()
        
        # 获取目标文件夹配置
        auto_get, target_folder_names, target_folder_fullpaths = self._get_target_folders()
        if target_folder_names is None:
            return
        
        # 获取用户输入参数
        config = self._get_user_config()
        
        # 创建目标文件夹（如果不存在）
        os.makedirs(config["destination_path"], exist_ok=True)
        
        # 扫描相似文件夹
        similar_folders = self.folder_manager.scan_similar_folders(
            config["source_paths"], 
            target_folder_names, 
            target_folder_fullpaths, 
            config["similarity_threshold"], 
            auto_get
        )
        
        # 处理结果
        self._process_results(similar_folders, config["destination_path"], auto_get)
    
    def _get_target_folders(self) -> tuple[bool, list[str] | None, list[str] | None]:
        """
        获取目标文件夹配置
        
        Returns:
            (是否自动获取, 目标文件夹名称列表, 目标文件夹完整路径列表)
        """
        auto_get = self.ui_manager.ask_auto_get()
        
        if auto_get:
            auto_dir = self.ui_manager.get_auto_dir()
            target_folder_names, target_folder_fullpaths = self.folder_manager.auto_get_target_folders(auto_dir)
            
            if target_folder_names is None:
                return auto_get, None, None
            
            self.ui_manager.display_target_folders(target_folder_names, target_folder_fullpaths)
        else:
            target_folder_names = self.ui_manager.get_manual_target_folders()
            target_folder_fullpaths = None
            self.ui_manager.display_target_folders(target_folder_names)
        
        return auto_get, target_folder_names, target_folder_fullpaths
    
    def _get_user_config(self) -> dict:
        """
        获取用户配置
        
        Returns:
            包含用户配置的字典
        """
        return {
            "source_paths": self.ui_manager.get_source_paths(),
            "destination_path": self.ui_manager.get_destination_path(),
            "similarity_threshold": self.ui_manager.get_similarity_threshold()
        }
    
    def _process_results(self, similar_folders: list[dict], destination_path: str, auto_get: bool):
        """
        处理扫描结果
        
        Args:
            similar_folders: 相似文件夹信息列表
            destination_path: 目标路径
            auto_get: 是否自动获取模式
        """
        if similar_folders:
            self.ui_manager.display_similar_folders(similar_folders, auto_get)
            output_choice = self.ui_manager.get_output_choice()
            
            output_paths = self.output_manager.generate_output_paths(
                similar_folders, 
                output_choice, 
                destination_path, 
                auto_get
            )
            
            self.output_manager.save_to_file(output_paths)

            # 构建配对数据
            pairs = self.pair_manager.build_pairs(similar_folders, auto_get, destination_path)

            # 是否保存 JSON
            if self.ui_manager.ask_save_pairs():
                json_filename = self.ui_manager.get_pairs_json_filename()
                self.pair_manager.save_pairs_to_json(pairs, json_filename)
                self.ui_manager.notify_pairs_saved(json_filename)

            # 是否执行移动
            if self.ui_manager.ask_move_contents():
                direction = self.ui_manager.get_move_direction()
                conflict = self.ui_manager.get_conflict_policy()
                result = self.pair_manager.move_contents(
                    pairs,
                    direction=direction,
                    conflict=conflict,
                    dry_run=False,
                )
                self.ui_manager.show_move_result(result.as_dict())
        else:
            self.ui_manager.show_no_results()
