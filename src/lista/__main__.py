#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
画师信息维护工具

这个工具专门用于维护和管理画师数据库，包括：
- 自动扫描并更新画师文件夹列表
- 添加、删除用户自定义画师
- 搜索和列出画师信息
- 显示画师统计信息

作者: Lista
创建时间: 2025年7月14日
"""

import os
import json
from pathlib import Path
from typing import Dict
from loguru import logger
import sys
from datetime import datetime

def setup_logger(app_name="app", project_root=None, console_output=True):
    """配置 Loguru 日志系统
    
    Args:
        app_name: 应用名称，用于日志目录
        project_root: 项目根目录，默认为当前文件所在目录
        console_output: 是否输出到控制台，默认为True
        
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
    
    # 有条件地添加控制台处理器（简洁版格式）
    if console_output:
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
        enqueue=True,     )
    
    # 创建配置信息字典
    config_info = {
        'log_file': log_file,
    }
    
    logger.info(f"日志系统已初始化，应用名称: {app_name}")
    return logger, config_info

logger, config_info = setup_logger(app_name="lista", console_output=True)


class ArtistInfoManager:
    """画师信息管理器 - 负责维护和管理画师数据库"""
    
    def __init__(self, config_path: str = None, artists_path: str = None):
        # 如果没有指定配置文件路径，则使用同目录下的默认配置文件
        if config_path is None:
            config_path = Path(__file__).parent / "config.json"
        if artists_path is None:
            artists_path = Path(__file__).parent / "artists.json"
        
        logger.info(f"初始化画师信息管理器，配置文件路径: {config_path}")
        logger.info(f"画师数据文件路径: {artists_path}")
        
        self.config_path = config_path
        self.artists_path = artists_path
        
        self.config = self._load_json_config(config_path)
        self.artists_data = self._load_json_config(artists_path)
        
        # 初始化默认配置结构（如果配置文件为空或不存在）
        if not self.config:
            logger.info("配置文件不存在或为空，使用默认配置")
            self.config = self._create_default_config()
            self._save_json_config(self.config, self.config_path)
        
        # 初始化默认画师数据结构（如果画师文件为空或不存在）
        if not self.artists_data:
            logger.info("画师数据文件不存在或为空，创建初始结构")
            self.artists_data = self._create_default_artists_data()
            self._save_artists_data()
        
        # 确保必要的数据结构存在
        if 'auto_detected' not in self.artists_data:
            self.artists_data['auto_detected'] = {}
        if 'user_defined' not in self.artists_data:
            self.artists_data['user_defined'] = {}
        if 'metadata' not in self.artists_data:
            self.artists_data['metadata'] = {
                'version': '1.0.0',
                'created_time': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'auto_detected_count': 0,
                'user_defined_count': 0,
                'total_artists': 0
            }
        
        self.base_dir = Path(self.config['paths']['base_dir'])
        logger.info(f"基础目录: {self.base_dir}")
        
        # 检查基础目录是否存在
        if not self.base_dir.exists():
            logger.warning(f"基础目录不存在: {self.base_dir}")
            logger.info("如果这是第一次运行，请确保配置文件中的基础目录路径正确")
            logger.info("或者手动创建该目录后再次运行程序")
            # 不直接抛出异常，而是继续运行，但跳过更新画师列表
            self._should_update_artists = False
        else:
            self._should_update_artists = True
        
        # 只有在基础目录存在时才初始化更新画师列表
        if self._should_update_artists:
            logger.info("开始初始化画师列表...")
            self.update_artist_list()
            
            # 打印当前的画师列表
            all_artists = {**self.artists_data['auto_detected'], 
                          **self.artists_data['user_defined']}
            logger.info(f"当前共有 {len(all_artists)} 个画师:")
            for name, folder in all_artists.items():
                logger.debug(f"  - {name} -> {folder}")
        else:
            logger.warning("跳过画师列表初始化，因为基础目录不存在")

    def _load_json_config(self, config_path: str) -> dict:
        """加载 JSON 配置文件"""
        if not os.path.exists(config_path):
            logger.warning(f"配置文件不存在: {config_path}")
            return {}
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 文件格式错误: {config_path} - {str(e)}")
            return {}
        except Exception as e:
            logger.error(f"读取配置文件失败: {config_path} - {str(e)}")
            return {}

    def _create_default_config(self) -> dict:
        """创建默认配置"""
        return {
            "paths": {
                "base_dir": "E:\\1EHV",
                "found_artists_dir": "E:\\1EHV\\[01已找到画师]"
            },
            "categories": {
                "CG": ["CG", "cg"],
                "漫画": ["漫画", "manga", "comic"],
                "插画": ["插画", "illust", "illustration"],
                "同人": ["同人", "doujin"],
                "原创": ["原创", "original"]
            },
            "exclude_keywords": [
                "汉化", "翻译", "Chinese", "中文", "简体", "繁体",
                "DL版", "无修正", "有修正", "高画质", "高清",
                ".zip", ".rar", ".7z"
            ]
        }
    
    def _create_default_artists_data(self) -> dict:
        """创建默认画师数据结构"""
        return {
            "metadata": {
                "version": "1.0.0",
                "created_time": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "auto_detected_count": 0,
                "user_defined_count": 0,
                "total_artists": 0,
                "description": "画师数据库 - 自动生成"
            },
            "auto_detected": {},
            "user_defined": {}
        }

    def _save_json_config(self, data: dict, config_path: str):
        """保存 JSON 配置文件"""
        # 更新时间戳
        if 'metadata' in data:
            data['metadata']['last_updated'] = datetime.now().isoformat()
        elif 'last_updated' in data:
            data['last_updated'] = datetime.now().isoformat()
            
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_artists_data(self):
        """保存画师数据到 JSON 文件"""
        # 更新统计信息
        self.artists_data['metadata']['auto_detected_count'] = len(self.artists_data['auto_detected'])
        self.artists_data['metadata']['user_defined_count'] = len(self.artists_data['user_defined'])
        self.artists_data['metadata']['total_artists'] = (
            self.artists_data['metadata']['auto_detected_count'] + 
            self.artists_data['metadata']['user_defined_count']
        )
        
        self._save_json_config(self.artists_data, self.artists_path)

    def update_artist_list(self):
        """更新画师列表"""
        logger.info("开始更新画师列表...")
        
        base_dir = Path(self.config['paths']['base_dir'])
        
        # 检查基础目录是否存在
        if not base_dir.exists():
            logger.error(f"基础目录不存在: {base_dir}")
            logger.info("请检查配置文件中的基础目录路径是否正确")
            return False
        
        try:
            # 获取所有画师文件夹
            folders = [f.name for f in base_dir.iterdir() 
                      if f.is_dir() and f.name.startswith('[') and 
                      not any(x in f.name for x in ['待分类', '已找到画师', '已存在画师', '去图', 'fanbox', 'COS'])]
            
            logger.info(f"找到 {len(folders)} 个画师文件夹")
            
            # 确保画师数据结构存在
            if 'auto_detected' not in self.artists_data:
                self.artists_data['auto_detected'] = {}
            if 'user_defined' not in self.artists_data:
                self.artists_data['user_defined'] = {}
            
            # 清理不存在的文件夹
            for folder in list(self.artists_data['auto_detected'].keys()):
                if folder not in folders:
                    logger.warning(f"移除不存在的文件夹: {folder}")
                    del self.artists_data['auto_detected'][folder]
            
            # 更新每个文件夹的画师名称数组
            for folder_name in folders:
                # 如果在用户自定义中已存在，则跳过
                if any(folder_name == v for v in self.artists_data['user_defined'].values()):
                    logger.debug(f"跳过用户自定义的文件夹: {folder_name}")
                    continue
                
                # 自动更新或添加画师名称数组
                # 去掉开头的 [ 和结尾的 ]
                clean_name = folder_name[1:-1] if folder_name.endswith(']') else folder_name[1:]
                
                # 提取所有名称（画师名和社团名）
                names = []
                if '(' in clean_name:
                    # 处理带括号的情况
                    circle_part = clean_name.split('(')[0].strip()
                    artist_part = clean_name.split('(')[1].rstrip(')').strip()
                    
                    # 先添加画师名（按顿号分割）
                    artist_names = [n.strip() for n in artist_part.split('、')]
                    names.extend(artist_names)
                    
                    # 再添加社团名（按顿号分割）
                    circle_names = [n.strip() for n in circle_part.split('、')]
                    names.extend(circle_names)
                else:
                    # 没有括号的情况，直接作为画师名
                    names = [clean_name]
                
                # 过滤掉无效名称
                valid_names = [name for name in names 
                             if name and not any(k in name for k in self.config['exclude_keywords'])]
                
                if valid_names:
                    if folder_name in self.artists_data['auto_detected']:
                        logger.info(f"更新画师名称: {folder_name} -> {valid_names}")
                    else:
                        logger.info(f"添加新画师: {folder_name} -> {valid_names}")
                    self.artists_data['auto_detected'][folder_name] = valid_names
            
            # 保存更新后的画师数据
            self._save_artists_data()
            
            total_artists = len(self.artists_data['auto_detected']) + len(self.artists_data['user_defined'])
            logger.info(f"画师列表更新完成，共 {total_artists} 个画师")
            logger.debug(f"自动检测: {len(self.artists_data['auto_detected'])} 个")
            logger.debug(f"用户自定义: {len(self.artists_data['user_defined'])} 个")
            return True
            
        except Exception as e:
            logger.error(f"扫描目录出错: {str(e)}")
            return False

    def add_user_defined_artist(self, artist_names: str, folder_name: str):
        """
        添加用户自定义画师
        
        Args:
            artist_names: 画师名称（多个名称用空格分隔）
            folder_name: 对应的文件夹名称
        """
        if artist_names in self.artists_data['user_defined']:
            logger.warning(f"画师已存在: {artist_names}")
            return False
        
        # 检查文件夹是否真实存在
        if not self.base_dir.exists():
            logger.error(f"基础目录不存在: {self.base_dir}")
            return False
            
        folder_path = self.base_dir / folder_name
        if not folder_path.exists():
            logger.error(f"文件夹不存在: {folder_path}")
            return False
        
        self.artists_data['user_defined'][artist_names] = folder_name
        self._save_artists_data()
        logger.info(f"已添加用户自定义画师: {artist_names} -> {folder_name}")
        return True
    
    def remove_user_defined_artist(self, artist_names: str):
        """
        删除用户自定义画师
        
        Args:
            artist_names: 要删除的画师名称
        """
        if artist_names not in self.artists_data['user_defined']:
            logger.warning(f"画师不存在: {artist_names}")
            return False
        
        folder_name = self.artists_data['user_defined'][artist_names]
        del self.artists_data['user_defined'][artist_names]
        self._save_artists_data()
        logger.info(f"已删除用户自定义画师: {artist_names} -> {folder_name}")
        return True
    
    def list_artists(self, artist_type: str = "all"):
        """
        列出画师信息
        
        Args:
            artist_type: 画师类型 ("all", "auto", "user")
        """
        logger.info(f"列出画师信息 (类型: {artist_type}):")
        
        if artist_type in ["all", "auto"]:
            logger.info(f"自动检测画师 ({len(self.artists_data['auto_detected'])} 个):")
            for folder, names in self.artists_data['auto_detected'].items():
                logger.info(f"  {folder} -> {names}")
        
        if artist_type in ["all", "user"]:
            logger.info(f"用户自定义画师 ({len(self.artists_data['user_defined'])} 个):")
            for names, folder in self.artists_data['user_defined'].items():
                logger.info(f"  {names} -> {folder}")
    
    def search_artist(self, keyword: str):
        """
        搜索画师
        
        Args:
            keyword: 搜索关键词
        """
        logger.info(f"搜索画师: {keyword}")
        found_artists = []
        
        # 搜索自动检测的画师
        for folder, names in self.artists_data['auto_detected'].items():
            if keyword.lower() in folder.lower() or any(keyword.lower() in name.lower() for name in names):
                found_artists.append(("auto", folder, names))
        
        # 搜索用户自定义的画师
        for names, folder in self.artists_data['user_defined'].items():
            if keyword.lower() in names.lower() or keyword.lower() in folder.lower():
                found_artists.append(("user", names, folder))
        
        if found_artists:
            logger.info(f"找到 {len(found_artists)} 个匹配的画师:")
            for artist_type, key, value in found_artists:
                if artist_type == "auto":
                    logger.info(f"  [自动] {key} -> {value}")
                else:
                    logger.info(f"  [用户] {key} -> {value}")
        else:
            logger.info("未找到匹配的画师")
        
        return found_artists


def main():
    """主函数 - 画师信息维护工具的命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="画师信息维护工具 - 管理和维护画师数据库")
    parser.add_argument("--config", "-c", help="配置文件路径", default=None)
    parser.add_argument("--artists", "-a", help="画师数据文件路径", default=None)
    parser.add_argument("--update-list", "-u", action="store_true", help="更新画师列表")
    parser.add_argument("--show-stats", "-s", action="store_true", help="显示画师统计信息")
    parser.add_argument("--list-artists", "-l", choices=["all", "auto", "user"], help="列出画师信息")
    parser.add_argument("--search", help="搜索画师（按关键词）")
    parser.add_argument("--add-artist", nargs=2, metavar=("NAMES", "FOLDER"), help="添加用户自定义画师 (画师名 文件夹名)")
    parser.add_argument("--remove-artist", help="删除用户自定义画师")
    
    args = parser.parse_args()
    
    try:
        # 初始化画师信息管理器
        manager = ArtistInfoManager(config_path=args.config, artists_path=args.artists)
        
        if args.update_list:
            # 更新画师列表
            logger.info("正在更新画师列表...")
            success = manager.update_artist_list()
            if success:
                logger.info("画师列表更新完成！")
            else:
                logger.error("画师列表更新失败！请检查基础目录配置")
        
        if args.show_stats:
            # 显示画师统计信息
            all_artists = {**manager.artists_data['auto_detected'], 
                          **manager.artists_data['user_defined']}
            logger.info(f"画师统计信息:")
            logger.info(f"- 自动检测画师: {len(manager.artists_data['auto_detected'])} 个")
            logger.info(f"- 用户自定义画师: {len(manager.artists_data['user_defined'])} 个")
            logger.info(f"- 总计: {len(all_artists)} 个画师")
        
        if args.list_artists:
            # 列出画师信息
            manager.list_artists(args.list_artists)
        
        if args.search:
            # 搜索画师
            manager.search_artist(args.search)
        
        if args.add_artist:
            # 添加画师
            artist_names, folder_name = args.add_artist
            manager.add_user_defined_artist(artist_names, folder_name)
        
        if args.remove_artist:
            # 删除画师
            manager.remove_user_defined_artist(args.remove_artist)
        
        if not any([args.update_list, args.show_stats, args.list_artists, 
                   args.search, args.add_artist, args.remove_artist]):
            # 如果没有指定任何操作，显示帮助信息
            parser.print_help()
            logger.info("请指定要执行的操作")
            
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}")
        raise


if __name__ == "__main__":
    main()

