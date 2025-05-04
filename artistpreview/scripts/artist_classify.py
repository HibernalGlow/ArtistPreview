from pickle import TRUE
import shutil
from pathlib import Path
import os
import re
import yaml
from typing import Dict, List, Optional, Tuple
import sys
import argparse
import pyperclip
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from nodes.tui.preset.textual_preset import create_config_app
from nodes.record.logger_config import setup_logger
from nodes.comic.classifier.artist_classifier import ArtistClassifier
config = {
    'script_name': 'artist_classify',
    'console_enabled': TRUE
}
logger, config_info = setup_logger(config)

def process_args():
    """处理命令行参数"""
    parser = argparse.ArgumentParser(description='画师分类工具')
    parser.add_argument('-c', '--clipboard', action='store_true',
                        help='使用剪贴板中的路径')
    parser.add_argument('-p', '--path', type=str,
                        help='指定待处理文件夹路径')
    parser.add_argument('--intermediate', action='store_true',
                        help='启用中间模式')
    parser.add_argument('--update-list', action='store_true',
                        help='更新画师列表')
    parser.add_argument('--text-mode', action='store_true',
                        help='启用文本模式')
    parser.add_argument('--create-folders', action='store_true',
                        help='在中间模式下创建画师文件夹')
    
    args = parser.parse_args()
    
    # 获取路径
    path = None
    if args.clipboard:
        try:
            path = pyperclip.paste().strip('"')
            logger.info(f"从剪贴板读取路径: {path}")
        except Exception as e:
            logger.error(f"无法读取剪贴板: {e}")
            sys.exit(1)
    elif args.path:
        path = args.path
    else:
        # 在文本模式下，自动查找同目录下的to_be_classified.txt
        if args.text_mode:
            default_txt = Path(__file__).parent / "to_be_classified.txt"
            if default_txt.exists():
                path = str(default_txt)
            else:
                path = None
    
    # 验证路径
    if path:
        path = path.strip('"').strip("'")  # 移除可能的引号
        if not os.path.exists(path):
            logger.error(f"路径不存在: {path}")
            sys.exit(1)
    
    return path, args

def run_classifier(path: Optional[str], args):
    """运行分类器"""
    try:
        classifier = ArtistClassifier()
        logger.info("画师分类器初始化完成")
        
        if args.update_list:
            logger.info("手动更新画师列表")
            classifier.update_artist_list()
        
        if path:
            try:
                classifier.set_pending_dir(path)
                logger.info(f"设置待处理目录: {path}")
            except ValueError as e:
                logger.error(str(e))
                return
            
            classifier.intermediate_mode = args.intermediate
            classifier.create_artist_folders = args.create_folders  # 设置是否创建画师文件夹
            classifier.process_files()
        else:
            # 创建TUI配置界面
            checkbox_options = [
                ("中间模式", "intermediate", "--intermediate"),
                ("更新画师列表", "update_list", "--update-list"),
                ("创建画师文件夹", "create_folders", "--create-folders"),  # 新增选项
            ]
            
            input_options = [
                ("待处理路径", "path", "-p", "", "输入待处理文件夹路径"),
            ]

            app = create_config_app(
                program=__file__,
                checkbox_options=checkbox_options,
                input_options=input_options,
                title="画师分类配置",
            )
            
            app.run()
    except Exception as e:
        logger.error(f"运行过程中出现错误: {e}")
        raise

def main():
    path, args = process_args()
    
    try:
        classifier = ArtistClassifier()
        logger.info("画师分类器初始化完成")
        
        # 更新画师列表
        if args.update_list:
            logger.info("手动更新画师列表")
            classifier.update_artist_list()
            return
        
        # 文本模式处理
        if args.text_mode or (path and path.endswith('to_be_classified.txt')):
            txt_path = Path(path) if path else Path(__file__).parent / "to_be_classified.txt"
            if not txt_path.exists():
                logger.error(f"文本文件不存在: {txt_path}")
                return
            
            result = classifier.process_to_be_classified(str(txt_path))
            output_path = txt_path.parent / 'classified_result.yaml'
            classifier.save_classification_result(result, str(output_path))
            return
        
        # 如果指定了路径，直接处理文件
        if path:
            try:
                classifier.set_pending_dir(path)
                logger.info(f"设置待处理目录: {path}")
                classifier.intermediate_mode = args.intermediate
                classifier.create_artist_folders = args.create_folders
                classifier.process_files()
                return
            except ValueError as e:
                logger.error(str(e))
                return
        
        # 如果没有任何参数，显示TUI界面
        checkbox_options = [
            ("中间模式", "intermediate", "--intermediate"),
            ("更新画师列表", "update_list", "--update-list"),
            ("文本模式", "text_mode", "--text-mode"),
            ("创建画师文件夹", "create_folders", "--create-folders"),
            ("使用剪贴板路径", "clipboard", "-c"),  # 新增剪贴板选项
        ]
        
        input_options = [
            ("待处理路径", "path", "-p", "", "输入待处理文件夹路径（如果使用剪贴板则忽略此项）"),
        ]

        app = create_config_app(
            program=__file__,
            checkbox_options=checkbox_options,
            input_options=input_options,
            title="画师分类配置",
        )
        
        app.run()
    except Exception as e:
        logger.error(f"运行过程中出现错误: {e}")
        raise

if __name__ == "__main__":
    main()
