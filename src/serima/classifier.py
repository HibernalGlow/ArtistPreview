"""
serima 核心分类功能模块
"""

import os
import re
import time
import shutil
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict

from .utils import (
    is_archive, is_archive_corrupted, normalize_chinese, 
    run_7z_command, IMAGE_EXTENSIONS, is_path_blacklisted,
    setup_logger
)

# 设置日志
logger = setup_logger('serima')

class MangaClassifier:
    """漫画压缩包分类器"""
    
    def __init__(self, category_folders=None, max_workers=16):
        """初始化分类器
        
        Args:
            category_folders: 分类文件夹列表，如果为None使用默认分类
            max_workers: 最大工作线程数
        """
        self.max_workers = max_workers
        
        # 默认分类目录
        self.default_categories = {
            'spread': ('广告', ['spread', 'advertisement']),
            'image': ('单图', ['single', 'solo']),
            'artbook': ('画集', ['artbook', 'art book', 'art-book', 'art_book', '畫集', 'CG集', 'pixiv']),
            'short': ('短篇', ['short', 'oneshot', 'one-shot', 'one_shot', 'short story']),
            'complete': ('完本', ['complete', 'complete works', 'completed', '完結', '完结']),
        }
        
        # 如果提供了自定义分类文件夹，使用它
        if category_folders:
            self.categories = self._parse_category_folders(category_folders)
        else:
            self.categories = self.default_categories
    
    def _parse_category_folders(self, folder_list):
        """解析用户提供的分类文件夹列表
        
        Args:
            folder_list: 文件夹列表 ["广告:spread,advertisement", "单图:single,solo", ...]
            
        Returns:
            解析后的分类字典
        """
        categories = {}
        for item in folder_list:
            if ':' in item:
                key, values = item.split(':', 1)
                display_name = key.strip()
                keywords = [k.strip().lower() for k in values.split(',')]
                # 使用第一个关键词作为分类key
                if keywords:
                    cat_key = keywords[0]
                    categories[cat_key] = (display_name, keywords)
            else:
                # 如果没有提供关键词，使用文件夹名本身
                display_name = item.strip()
                cat_key = display_name.lower()
                categories[cat_key] = (display_name, [cat_key])
        
        return categories
    
    def _get_archive_info(self, archive_path):
        """获取压缩包的信息
        
        Args:
            archive_path: 压缩包路径
            
        Returns:
            包含文件列表和图片数量的字典
        """
        # 获取压缩包内容列表
        try:
            file_list_output = run_7z_command('l', archive_path, "列出压缩包内容")
            
            # 解析文件列表
            files = []
            image_count = 0
            
            # 如果获取到输出
            if file_list_output:
                # 正则匹配每行
                for line in file_list_output.splitlines():
                    # 尝试提取文件路径
                    parts = line.split()
                    if len(parts) >= 5:  # 确保有足够的部分
                        # 文件路径通常是最后一项
                        file_path = parts[-1]
                        if '.' in file_path:  # 检查是否有扩展名
                            # 检查是否是图像文件
                            _, ext = os.path.splitext(file_path)
                            if ext.lower() in IMAGE_EXTENSIONS:
                                image_count += 1
                            files.append(file_path)
            
            return {
                "files": files,
                "image_count": image_count,
            }
        
        except Exception as e:
            logger.error(f"获取压缩包信息失败 {archive_path}: {str(e)}")
            return {"files": [], "image_count": 0}
    
    def classify_archive(self, archive_path):
        """对单个压缩包进行分类
        
        Args:
            archive_path: 压缩包路径
            
        Returns:
            分类结果，如果无法分类则返回None
        """
        try:
            if not os.path.exists(archive_path):
                logger.warning(f"文件不存在: {archive_path}")
                return None
            
            # 检查是否是支持的压缩包
            if not is_archive(archive_path):
                logger.warning(f"不支持的文件格式: {archive_path}")
                return None
            
            # 检查压缩包是否损坏
            if is_archive_corrupted(archive_path):
                logger.warning(f"压缩包已损坏: {archive_path}")
                return "corrupted"  # 特殊标记，表示损坏的压缩包
            
            # 获取压缩包信息
            archive_info = self._get_archive_info(archive_path)
            files = archive_info["files"]
            image_count = archive_info["image_count"]
            
            # 获取文件名（不含路径和扩展名）
            filename = os.path.basename(archive_path)
            name_without_ext = os.path.splitext(filename)[0]
            
            # 标准化文件名（转换为小写以便比较）
            lower_name = name_without_ext.lower()
            # 标准化中文（转换为简体）
            normalized_name = normalize_chinese(lower_name)
            
            # 判断分类
            result = None
            
            # 根据图片数量判断是否为单图
            is_single = image_count <= 1
            
            # 根据关键词分类
            for category_key, (display_name, keywords) in self.categories.items():
                # 检查文件名中是否包含分类关键词
                for keyword in keywords:
                    if keyword.lower() in normalized_name:
                        # 特殊情况：如果是完本和短篇的关键词重复，则更具体的分类优先
                        if (category_key == 'complete' and result == 'short') or \
                           (category_key == 'short' and result == 'complete'):
                            # 保留原始分类
                            pass
                        else:
                            result = category_key
                            break
                
                # 如果已经找到分类，跳出循环
                if result:
                    break
            
            # 如果尚未分类且只有单图，归为单图分类
            if not result and is_single:
                result = 'image'
            
            # 如果图片数量特别少或者特别多，可能是特殊情况
            if not result:
                if image_count < 5:
                    if any(keyword in normalized_name for keyword in ['pixiv', 'fanbox']):
                        result = 'artbook'  # Pixiv或Fanbox通常是画集
                    else:
                        result = 'image'  # 图片较少，归为单图
                elif image_count > 100:
                    result = 'artbook'  # 图片量大，可能是画集
            
            # 如果无法确定分类，返回None
            return result
            
        except Exception as e:
            logger.error(f"分类压缩包时出错 {archive_path}: {str(e)}")
            return None
    
    def process_directory(self, input_dir, output_dir=None, recursive=False):
        """处理指定目录中的所有压缩包
        
        Args:
            input_dir: 输入目录
            output_dir: 输出目录，如果为None则使用输入目录
            recursive: 是否递归处理子目录
            
        Returns:
            处理结果统计
        """
        # 如果没有指定输出目录，使用输入目录
        if output_dir is None:
            output_dir = input_dir
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 收集所有压缩包
        archives = []
        # 记录目录结构，以便后续集中显示进度
        dirs_to_process = []
        
        # 遍历目录
        if recursive:
            # 递归模式：遍历所有子目录
            for root, dirs, files in os.walk(input_dir):
                # 忽略黑名单中的路径
                if is_path_blacklisted(root):
                    continue
                
                # 记录当前目录的压缩包
                dir_archives = []
                for file in files:
                    if is_archive(file):
                        full_path = os.path.join(root, file)
                        dir_archives.append(full_path)
                
                if dir_archives:
                    archives.extend(dir_archives)
                    dirs_to_process.append((root, len(dir_archives)))
                    logger.info(f"找到目录: {root} ({len(dir_archives)}个压缩包)")
        else:
            # 非递归模式：只处理当前目录
            for file in os.listdir(input_dir):
                if is_archive(file):
                    full_path = os.path.join(input_dir, file)
                    archives.append(full_path)
            
            dirs_to_process.append((input_dir, len(archives)))
            logger.info(f"找到 {len(archives)} 个压缩包")
        
        # 如果没有找到压缩包，直接返回
        if not archives:
            logger.info("没有找到需要处理的压缩包")
            return {"total": 0, "processed": 0, "skipped": 0, "errors": 0, "categories": {}}
        
        # 创建分类目录
        category_paths = {}
        corrupted_path = os.path.join(output_dir, "损坏压缩包")
        
        # 为每个分类创建目录
        for category_key, (display_name, _) in self.categories.items():
            category_path = os.path.join(output_dir, display_name)
            os.makedirs(category_path, exist_ok=True)
            category_paths[category_key] = category_path
        
        # 创建损坏压缩包目录
        os.makedirs(corrupted_path, exist_ok=True)
        
        # 初始化计数器
        stats = {
            "total": len(archives),
            "processed": 0,
            "skipped": 0,
            "errors": 0,
            "categories": defaultdict(int)
        }
        
        # 开始处理压缩包
        logger.info(f"开始处理 {len(archives)} 个压缩包...")
        
        # 使用线程池加速处理
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_archive = {executor.submit(self.classify_archive, archive): archive for archive in archives}
            
            # 收集结果
            for i, future in enumerate(future_to_archive, 1):
                archive_path = future_to_archive[future]
                filename = os.path.basename(archive_path)
                
                # 显示进度
                logger.info(f"处理中... ({i}/{len(archives)}) {i/len(archives)*100:.1f}% - {filename}")
                
                try:
                    # 获取分类结果
                    category = future.result()
                    
                    # 处理结果
                    if category is None:
                        logger.warning(f"无法分类: {filename}")
                        stats["skipped"] += 1
                    elif category == "corrupted":
                        # 移动损坏的压缩包
                        target_path = os.path.join(corrupted_path, filename)
                        if os.path.exists(target_path):
                            base, ext = os.path.splitext(target_path)
                            counter = 1
                            while os.path.exists(f"{base}_{counter}{ext}"):
                                counter += 1
                            target_path = f"{base}_{counter}{ext}"
                        
                        shutil.move(archive_path, target_path)
                        stats["categories"]["corrupted"] += 1
                        logger.info(f"移动损坏压缩包: {filename} -> 损坏压缩包/")
                    else:
                        # 获取目标路径
                        target_path = os.path.join(category_paths[category], filename)
                        
                        # 如果目标路径已存在，添加数字后缀
                        if os.path.exists(target_path):
                            base, ext = os.path.splitext(target_path)
                            counter = 1
                            while os.path.exists(f"{base}_{counter}{ext}"):
                                counter += 1
                            target_path = f"{base}_{counter}{ext}"
                        
                        # 移动文件
                        shutil.move(archive_path, target_path)
                        stats["categories"][category] += 1
                        
                        # 获取分类显示名
                        display_name = self.categories[category][0]
                        logger.info(f"分类完成: {filename} -> {display_name}/")
                    
                    stats["processed"] += 1
                    
                except Exception as e:
                    logger.error(f"处理出错: {filename} - {str(e)}")
                    stats["errors"] += 1
        
        # 显示统计信息
        logger.info(f"\n处理完成: {stats['processed']}/{stats['total']} 个压缩包")
        logger.info(f"跳过: {stats['skipped']} 个")
        logger.info(f"出错: {stats['errors']} 个")
        
        # 显示分类统计
        logger.info("\n分类统计:")
        for category_key, count in stats["categories"].items():
            if category_key == "corrupted":
                logger.info(f"  损坏压缩包: {count} 个")
            else:
                display_name = self.categories[category_key][0]
                logger.info(f"  {display_name}: {count} 个")
        
        return stats