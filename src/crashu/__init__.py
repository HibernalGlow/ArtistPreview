"""
Crashu - 文件夹相似度检测与批量移动工具

这是一个用于检测文件夹相似度并生成移动路径的工具包。

主要模块：
- folder_manager: 文件夹管理功能
- ui_manager: 用户界面管理
- output_manager: 输出管理
- app_controller: 应用程序控制器
- config: 配置管理

使用方法：
    from crashu import AppController
    app = AppController()
    app.run()
"""

from .core.app_controller import AppController
from .core.folder_manager import FolderManager
from .core.ui_manager import UIManager
from .core.output_manager import OutputManager
from .core.config import ConfigManager, AppConfig

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

__all__ = [
    "AppController",
    "FolderManager", 
    "UIManager",
    "OutputManager",
    "ConfigManager",
    "AppConfig"
]