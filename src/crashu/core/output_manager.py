"""
输出管理器模块
负责结果输出和文件保存
"""
import os
from rich.console import Console
from .config import ConfigManager

console = Console()


class OutputManager:
    """输出管理器"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_config()
    
    def generate_output_paths(
        self,
        similar_folders: list[dict], 
        output_choice: str, 
        destination_path: str, 
        auto_get: bool
    ) -> list[str]:
        """
        生成输出路径列表
        
        Args:
            similar_folders: 相似文件夹信息列表
            output_choice: 输出选择 ("1" 或 "2")
            destination_path: 目标路径
            auto_get: 是否自动获取模式
            
        Returns:
            输出路径列表
        """
        output_paths = []
        console.print(f"\n[bold {self.config.colors['success']}]重复文件夹路径列表：[/bold {self.config.colors['success']}]")
        
        for i, folder in enumerate(similar_folders, 1):
            if output_choice == "1":
                # 输出原文件夹路径
                out_path = folder["path"]
                console.print(f"{i}. ", end="")
                console.print(out_path, markup=False)
                output_paths.append(out_path)
            else:
                # 输出目标文件夹路径
                if auto_get and folder.get("target_fullpath"):
                    # 自动获取模式：target_fullpath 就是目标路径，不需要再添加 folder["name"]
                    destination = folder["target_fullpath"]
                else:
                    # 手动输入模式：需要组合 destination_path + target + name
                    target_subfolder = os.path.join(destination_path, folder["target"])
                    destination = os.path.join(target_subfolder, folder["name"])
                
                console.print(f"{i}. ", end="")
                console.print(destination, markup=False)
                output_paths.append(destination)
        
        return output_paths
    
    def save_to_file(self, output_paths: list[str], filename: str = None):
        """
        保存路径到文件
        
        Args:
            output_paths: 输出路径列表
            filename: 输出文件名（可选，使用配置中的默认值）
        """
        if filename is None:
            filename = self.config.output_filename
            
        try:
            with open(filename, "w", encoding="utf-8") as f:
                for path in output_paths:
                    f.write(path + "\n")
            
            console.print(f"\n[{self.config.colors['success']}]路径已写入 {filename}，每行一个，便于复制。[/{self.config.colors['success']}]")
            
        except Exception as e:
            console.print(f"[{self.config.colors['error']}]写入 {filename} 失败: {str(e)}[/{self.config.colors['error']}]")
