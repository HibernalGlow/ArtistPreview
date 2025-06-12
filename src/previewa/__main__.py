from typing import Dict, List, Any, Optional
from loguru import logger

from .core.classifier import ArtistClassifier
from .core.artist_db import ArtistDatabase
from .io.path_source import PathSource
from .io.output import OutputHandler
from .modes.standard import StandardMode
from .modes.intermediate import IntermediateMode
from .modes.text_mode import TextMode
from loguru import logger
import os
import sys
from pathlib import Path
from datetime import datetime

def setup_logger(app_name="app", project_root=None):
    """配置 Loguru 日志系统
    
    Args:
        app_name: 应用名称，用于日志目录
        project_root: 项目根目录，默认为当前文件所在目录
        
    Returns:
        tuple: (logger, config_info)
            - logger: 配置好的 logger 实例
            - config_info: 包含日志配置信息的字典
    """
    # 获取项目根目录
    if project_root is None:
        project_root = Path(__file__).parent.resolve()
    
    # 清除默认处理器
    logger.remove()
    
    # 添加控制台处理器（简洁版格式）
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <blue>{elapsed}</blue> | <level>{level.icon} {level: <8}</level> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>"
    )
    
    # 使用 datetime 构建日志路径
    current_time = datetime.now()
    date_str = current_time.strftime("%Y-%m-%d")
    hour_str = current_time.strftime("%H")
    minute_str = current_time.strftime("%M%S")
    
    # 构建日志目录和文件路径
    log_dir = os.path.join(project_root, "logs", app_name, date_str, hour_str)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{minute_str}.log")
    
    # 添加文件处理器
    logger.add(
        log_file,
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {elapsed} | {level.icon} {level: <8} | {name}:{function}:{line} - {message}",
    )
    
    # 创建配置信息字典
    config_info = {
        'log_file': log_file,
    }
    
    logger.info(f"日志系统已初始化，应用名称: {app_name}")
    return logger, config_info

logger, config_info = setup_logger(app_name="artist-preview")
class ArtistPreviewController:
    """
    ArtistPreview 主控制器，连接各个子模块并提供统一接口
    """
    
    def __init__(self, cache_path: Optional[str] = None):
        """
        初始化控制器
        
        参数:
            cache_path: 画师缓存文件路径，如不提供则使用默认路径
        """
        # 初始化组件
        self.artist_db = ArtistDatabase(cache_path)
        self.classifier = ArtistClassifier(self.artist_db)
        self.output_handler = OutputHandler()
        
        logger.info("ArtistPreview控制器已初始化")
    
    def update_artist_database(self) -> Dict[str, str]:
        """
        更新画师数据库
        
        返回:
            更新后的画师匹配模式字典
        """
        logger.info("正在更新画师列表")
        patterns = self.classifier.update_artist_list()
        logger.info(f"画师列表更新完成，共 {len(patterns)} 个画师")
        return patterns
    
    def classify(self, 
                mode: str = "standard", 
                source_type: str = "cli",
                source_data: Any = None, 
                **kwargs) -> Dict[str, Any]:
        """
        统一的分类入口方法
        
        参数:
            mode: 分类模式 ("standard", "intermediate", "text")
            source_type: 输入源类型 ("cli", "clipboard", "file")
            source_data: 输入源数据
            **kwargs: 传递给具体模式的额外参数
        
        返回:
            包含分类结果的字典
        """
        logger.info(f"开始分类，模式: {mode}, 来源: {source_type}")
        
        # 1. 获取输入路径
        path_source = PathSource(source_type, source_data)
        paths = path_source.get_paths()
        
        if not paths:
            logger.warning("没有找到有效的文件路径")
            return {
                "status": "error",
                "message": "没有找到有效的文件路径",
                "total_files": 0
            }
        
        logger.info(f"找到 {len(paths)} 个文件需要处理")
        
        # 2. 根据模式选择处理器
        if mode == "standard":
            processor = StandardMode(self.classifier)
        elif mode == "intermediate":
            create_folders = kwargs.get("create_folders", False)
            processor = IntermediateMode(self.classifier, create_folders=create_folders)
        elif mode == "text":
            processor = TextMode(self.classifier)
        else:
            logger.error(f"不支持的模式: {mode}")
            return {
                "status": "error",
                "message": f"不支持的模式: {mode}",
                "total_files": len(paths)
            }
            
        # 3. 执行分类
        result = processor.process(paths, **kwargs)
        
        # 4. 输出处理
        self.output_handler.print_summary(result)
        
        # 添加状态信息
        result["status"] = "success"
        
        logger.info("分类完成")
        return result

# 用作命令行入口的函数
def main():
    """命令行入口函数"""
    from .ui.cli import parse_args, setup_logging
    
    args = parse_args()
    setup_logging(args.verbose)
    
    # 初始化控制器
    controller = ArtistPreviewController(args.cache_file)
    
    # 处理更新画师列表的情况
    if args.update_list:
        controller.update_artist_database()
        return 0
        
    # 确定输入源类型和数据
    if args.clipboard:
        source_type = "clipboard"
        source_data = None
    elif args.path:
        source_type = "cli"
        source_data = args.path
    elif args.text_mode:
        source_type = "file"
        source_data = args.text_file
    else:
        # 没有指定输入源，启动TUI
        from .ui.tui import start_tui
        result = start_tui(controller)
        return 0 if result.get("status") != "error" else 1
    
    # 确定分类模式
    if args.text_mode:
        mode = "text"
        kwargs = {"output_file": args.output_file}
    elif args.intermediate:
        mode = "intermediate"
        kwargs = {
            "create_folders": args.create_folders,
            "output_dir": args.output_dir
        }
    else:
        mode = "standard"
        kwargs = {"output_dir": args.output_dir} if args.output_dir else {}
        
    # 执行分类
    result = controller.classify(
        mode=mode,
        source_type=source_type,
        source_data=source_data,
        **kwargs
    )
    
    return 0 if result.get("status") != "error" else 1