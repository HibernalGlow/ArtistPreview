"""
用户界面管理器模块
负责所有用户交互和界面显示
"""
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table
from .folder_manager import FolderManager
from .config import ConfigManager

console = Console()


class UIManager:
    """用户界面管理器"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_config()
    
    def show_header(self):
        """显示程序头部"""
        console.print(Panel(
            f"[bold cyan]{self.config.header_title}[/bold cyan]", 
            border_style=self.config.header_border_style
        ))
    
    def ask_auto_get(self) -> bool:
        """
        询问是否自动获取目标文件夹
        
        Returns:
            是否自动获取
        """
        return Confirm.ask(
            "是否自动获取目标文件夹（从指定目录下的一级子目录）？", 
            default=True
        )
    
    def get_auto_dir(self) -> str:
        """
        获取自动获取目录
        
        Returns:
            自动获取目录路径
        """
        return Prompt.ask(
            "请输入用于自动获取目标文件夹的目录", 
            default=self.config.default_auto_dir
        )
    
    def display_target_folders(
        self, 
        target_folder_names: list[str], 
        target_folder_fullpaths: list[str] | None = None
    ):
        """
        显示目标文件夹
        
        Args:
            target_folder_names: 目标文件夹名称列表
            target_folder_fullpaths: 目标文件夹完整路径列表（可选）
        """
        if target_folder_fullpaths:
            table = Table(title="自动获取的目标文件夹")
            table.add_column("序号", justify="center", style=self.config.colors["accent"])
            table.add_column("文件夹名称", style=self.config.colors["success"])
            table.add_column("完整路径", style="blue")
            
            for i, (name, fullpath) in enumerate(zip(target_folder_names, target_folder_fullpaths), 1):
                table.add_row(str(i), name, fullpath)
        else:
            table = Table(title="目标文件夹名称")
            table.add_column("序号", justify="center", style=self.config.colors["accent"])
            table.add_column("文件夹名称", style=self.config.colors["success"])
            
            for i, name in enumerate(target_folder_names, 1):
                table.add_row(str(i), name)
        
        console.print(table)
    
    def get_manual_target_folders(self) -> list[str]:
        """
        获取手动输入的目标文件夹
        
        Returns:
            目标文件夹名称列表
        """
        console.print(f"[{self.config.colors['info']}]请输入多个目标文件夹名称[/{self.config.colors['info']}] (每行一个，输入空行结束)")
        return FolderManager.get_multiline_input("请输入多个目标文件夹名称")
    
    def get_source_paths(self) -> list[str]:
        """
        获取源文件夹路径
        
        Returns:
            源文件夹路径列表
        """
        console.print(f"[{self.config.colors['info']}]请输入多个源文件夹路径[/{self.config.colors['info']}] (每行一个，输入空行结束，默认为{self.config.default_source_path})")
        source_paths = FolderManager.get_multiline_input("请输入多个源文件夹路径")
        
        if not source_paths:
            source_paths = [self.config.default_source_path]
        
        return source_paths
    
    def get_destination_path(self) -> str:
        """
        获取目标文件夹路径
        
        Returns:
            目标文件夹路径
        """
        return Prompt.ask(
            f"[{self.config.colors['info']}]请输入目标文件夹路径[/{self.config.colors['info']}] (默认为{self.config.default_destination_path})", 
            default=self.config.default_destination_path
        )
    
    def get_similarity_threshold(self) -> float:
        """
        获取相似度阈值
        
        Returns:
            相似度阈值
        """
        return float(Prompt.ask(
            f"[{self.config.colors['info']}]请输入相似度阈值[/{self.config.colors['info']}] (0-1之间，默认{self.config.default_similarity_threshold})", 
            default=str(self.config.default_similarity_threshold)
        ))
    
    def display_similar_folders(self, similar_folders: list[dict], auto_get: bool):
        """
        显示找到的相似文件夹
        
        Args:
            similar_folders: 相似文件夹信息列表
            auto_get: 是否自动获取模式
        """
        table = Table(title="找到的相似文件夹")
        table.add_column("序号", justify="center", style=self.config.colors["accent"])
        table.add_column("文件夹名称", style=self.config.colors["success"])
        table.add_column("文件夹路径", style="blue")
        table.add_column("目标匹配", style="magenta")
        table.add_column("相似度", justify="right", style=self.config.colors["warning"])
        
        if auto_get:
            table.add_column("目标完整路径", style="blue")
        
        for i, folder in enumerate(similar_folders, 1):
            row = [
                str(i),
                folder["name"],
                folder["path"],
                folder["target"],
                f"{folder['similarity']:.2f}"
            ]
            
            if auto_get:
                row.append(folder.get("target_fullpath", ""))
            
            table.add_row(*row)
        
        console.print(table)
    
    def get_output_choice(self) -> str:
        """
        获取输出选择
        
        Returns:
            输出选择 ("1" 或 "2")
        """
        console.print(f"\n[{self.config.colors['highlight']}]输出选项：[/{self.config.colors['highlight']}]")
        console.print(f"[{self.config.colors['accent']}]1. 输出原文件夹路径[/{self.config.colors['accent']}]")
        console.print(f"[{self.config.colors['accent']}]2. 输出目标文件夹路径[/{self.config.colors['accent']}]")
        
        return Prompt.ask(
            f"[bold {self.config.colors['warning']}]选择输出格式[/bold {self.config.colors['warning']}]",
            choices=["1", "2"],
            default="1"
        )
    
    def show_no_results(self):
        """显示无结果信息"""
        console.print(f"[{self.config.colors['warning']}]未找到符合条件的相似文件夹[/{self.config.colors['warning']}]")
