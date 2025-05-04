import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from loguru import logger

def start_tui(controller) -> Dict[str, Any]:
    """
    启动文本用户界面
    
    参数:
        controller: 主控制器实例
    
    返回:
        处理结果字典
    """
    logger.info("启动文本用户界面")
    
    print("\n===== ArtistPreview - 漫画/插图作品按画师分类工具 =====\n")
    
    # 选择操作类型
    print("请选择操作类型:")
    print("1. 按画师分类文件")
    print("2. 更新画师列表")
    print("3. 退出程序")
    
    while True:
        choice = input("\n请输入选项编号 [1-3]: ").strip()
        if choice in ["1", "2", "3"]:
            break
        print("无效选项，请重新输入")
    
    if choice == "3":
        print("退出程序")
        return {"status": "exit"}
    
    if choice == "2":
        print("\n正在更新画师列表...")
        controller.update_artist_database()
        print("画师列表更新完成")
        return {"status": "updated"}
    
    # 下面处理文件分类操作
    
    # 选择路径来源
    print("\n请选择文件路径来源:")
    print("1. 手动输入路径")
    print("2. 从剪贴板获取")
    print("3. 从文本文件获取")
    
    while True:
        source_choice = input("\n请输入选项编号 [1-3]: ").strip()
        if source_choice in ["1", "2", "3"]:
            break
        print("无效选项，请重新输入")
    
    source_type = ""
    source_data = None
    
    if source_choice == "1":
        path = input("\n请输入文件或文件夹路径: ").strip()
        if not path or not os.path.exists(path):
            print(f"路径不存在: {path}")
            return {"status": "error", "message": f"路径不存在: {path}"}
        source_type = "cli"
        source_data = path
    elif source_choice == "2":
        source_type = "clipboard"
    else:  # source_choice == "3"
        text_file = input("\n请输入包含路径列表的文本文件路径 [默认: to_be_classified.txt]: ").strip()
        if not text_file:
            text_file = "to_be_classified.txt"
        if not os.path.exists(text_file):
            print(f"文件不存在: {text_file}")
            return {"status": "error", "message": f"文件不存在: {text_file}"}
        source_type = "file"
        source_data = text_file
    
    # 选择分类模式
    print("\n请选择分类模式:")
    print("1. 标准模式 - 直接将文件移动到对应画师目录")
    print("2. 中间模式 - 移动到中间目录，可选是否创建画师子文件夹")
    print("3. 文本模式 - 生成分类结果YAML不移动文件")
    
    while True:
        mode_choice = input("\n请输入选项编号 [1-3]: ").strip()
        if mode_choice in ["1", "2", "3"]:
            break
        print("无效选项，请重新输入")
    
    mode = ""
    kwargs = {}
    
    if mode_choice == "1":
        mode = "standard"
        output_dir = input("\n请输入输出基础目录 [默认: 自动选择]: ").strip()
        if output_dir:
            kwargs["output_dir"] = output_dir
    elif mode_choice == "2":
        mode = "intermediate"
        output_dir = input("\n请输入中间输出目录 [默认: {输入路径}/分类结果]: ").strip()
        if output_dir:
            kwargs["output_dir"] = output_dir
        
        while True:
            create_folders = input("\n是否创建画师文件夹? (y/n) [默认: n]: ").strip().lower()
            if not create_folders or create_folders in ["y", "n"]:
                break
            print("无效选项，请输入 y 或 n")
        
        kwargs["create_folders"] = (create_folders == "y")
    else:  # mode_choice == "3"
        mode = "text"
        output_file = input("\n请输入输出YAML文件路径 [默认: classified_result.yaml]: ").strip()
        if not output_file:
            output_file = "classified_result.yaml"
        kwargs["output_file"] = output_file
    
    # 执行分类
    print("\n正在执行分类...")
    logger.info(f"TUI: 执行分类 - 模式: {mode}, 来源: {source_type}")
    
    result = controller.classify(
        mode=mode,
        source_type=source_type,
        source_data=source_data,
        **kwargs
    )
    
    print("\n分类完成!")
    
    if mode == "text":
        print(f"结果已保存到: {kwargs.get('output_file', 'classified_result.yaml')}")
    elif mode == "intermediate":
        create_folders = kwargs.get("create_folders", False)
        print(f"文件已移动到中间目录，{'已' if create_folders else '未'}创建画师文件夹")
    else:
        print("文件已分类到对应画师目录")
        
    return result