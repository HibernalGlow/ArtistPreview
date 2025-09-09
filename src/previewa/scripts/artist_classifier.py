import os
import re
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from venv import logger
import yaml
logger = logging.getLogger(__name__)

class ArtistClassifier:
    def __init__(self, config_path: str = None):
        # 如果没有指定配置文件路径，则使用同目录下的默认配置文件
        if config_path is None:
            config_path = Path(__file__).parent / "artist_classifier.yaml"
        
        logger.info(f"初始化画师分类器，配置文件路径: {config_path}")
        self.config = self._load_config(config_path)
        self.base_dir = Path(self.config['paths']['base_dir'])
        logger.info(f"基础目录: {self.base_dir}")
        
        # 确保基础目录存在
        if not self.base_dir.exists():
            logger.error(f"基础目录不存在: {self.base_dir}")
            raise ValueError(f"基础目录不存在: {self.base_dir}")
        
        self.found_artists_dir = Path(self.config['paths']['found_artists_dir'])
        self.intermediate_mode = False
        self.create_artist_folders = False  # 新增：是否创建画师文件夹的标志
        
        
        # 初始化时更新画师列表
        logger.info("开始初始化画师列表...")
        self.update_artist_list()
        
        # 打印当前的画师列表
        all_artists = {**self.config['artists']['auto_detected'], 
                      **self.config['artists']['user_defined']}
        logger.info(f"当前共有 {len(all_artists)} 个画师:")
        for name, folder in all_artists.items():
            logger.debug(f"  - {name} -> {folder}")

    def set_pending_dir(self, path: str):
        """设置待处理文件夹路径"""
        self.pending_dir = Path(path)
        if not self.pending_dir.exists():
            raise ValueError(f"路径不存在: {path}")

    def _load_config(self, config_path: str) -> dict:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _save_config(self, config_path: str):
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, allow_unicode=True)

    def update_artist_list(self):
        """更新画师列表"""
        logger.info("开始更新画师列表...")
        
        base_dir = Path(r'E:\1Hub\EH\1EHV')
        # logger.debug(f"扫描目录: {base_dir}")
        
        try:
            # 获取所有画师文件夹
            folders = [f.name for f in base_dir.iterdir() 
                      if f.is_dir() and f.name.startswith('[') and 
                      not any(x in f.name for x in ['待分类', '已找到画师', '已存在画师', '去图', 'fanbox', 'COS'])]
            
            logger.info(f"找到 {len(folders)} 个画师文件夹")
            
            # 确保配置中有必要的结构
            if 'artists' not in self.config:
                self.config['artists'] = {}
            if 'auto_detected' not in self.config['artists']:
                self.config['artists']['auto_detected'] = {}
            if 'user_defined' not in self.config['artists']:
                self.config['artists']['user_defined'] = {}
            
            # 清理不存在的文件夹
            for folder in list(self.config['artists']['auto_detected'].keys()):
                if folder not in folders:
                    logger.warning(f"移除不存在的文件夹: {folder}")
                    del self.config['artists']['auto_detected'][folder]
            
            # 更新每个文件夹的画师名称数组
            for folder_name in folders:
                # 如果在用户自定义中已存在，则跳过
                if any(folder_name == v for v in self.config['artists']['user_defined'].values()):
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
                    if folder_name in self.config['artists']['auto_detected']:
                        logger.info(f"更新画师名称: {folder_name} -> {valid_names}")
                    else:
                        logger.info(f"添加新画师: {folder_name} -> {valid_names}")
                    self.config['artists']['auto_detected'][folder_name] = valid_names
            
            # 保存更新后的配置
            self._save_config("画师分类.yaml")
            
            total_artists = len(self.config['artists']['auto_detected']) + len(self.config['artists']['user_defined'])
            logger.info(f"画师列表更新完成，共 {total_artists} 个画师")
            logger.debug(f"自动检测: {len(self.config['artists']['auto_detected'])} 个")
            logger.debug(f"用户自定义: {len(self.config['artists']['user_defined'])} 个")
            
        except Exception as e:
            logger.error(f"扫描目录出错: {str(e)}")
            raise

    def _detect_category(self, file_path: str) -> str:
        """根据文件路径检测作品类别"""
        path_str = str(file_path).lower()
        for category, keywords in self.config['categories'].items():
            # 检查完整路径中是否包含关键词
            if any(keyword.lower() in path_str for keyword in keywords):
                return category
        return "一般"

    def _find_artist_info(self, filename: str) -> Optional[Tuple[str, str, bool]]:
        """
        查找画师信息的公共函数
        
        Args:
            filename: 文件名
            
        Returns:
            Optional[Tuple[str, str, bool]]: (画师名, 文件夹名, 是否为已存在画师)
            如果未找到则返回None
        """
        # 从文件名中提取画师名称
        name_str = filename
        for keyword in self.config['exclude_keywords']:
            name_str = name_str.replace(keyword, "")
        
        # 提取方括号中的内容
        pattern = r'\[([^\[\]]+)\]'
        matches = re.finditer(pattern, name_str)
        artist_names = []
        
        for match in matches:
            content = match.group(1).strip()
            if '(' in content:
                # 处理带括号的情况
                circle_part = content.split('(')[0].strip()
                artist_part = content.split('(')[1].rstrip(')').strip()
                
                # 先添加画师名
                artist_names.extend([n.strip() for n in artist_part.split('、')])
                # 再添加社团名
                artist_names.extend([n.strip() for n in circle_part.split('、')])
            else:
                # 没有括号的情况
                artist_names.append(content)
        
        logger.debug(f"从文件名提取的画师名称: {artist_names}")
        
        # 先检查用户自定义的画师
        for artist_name in artist_names:
            if artist_name and not any(k in artist_name for k in self.config['exclude_keywords']):
                for names, folder in self.config['artists']['user_defined'].items():
                    if artist_name in names.split():
                        logger.info(f"找到用户自定义画师: {artist_name} ({names}) -> {folder}")
                        return artist_name, folder, True
        
        # 如果用户自定义中没找到，再检查自动检测的画师
        for artist_name in artist_names:
            if artist_name and not any(k in artist_name for k in self.config['exclude_keywords']):
                for folder, names in self.config['artists']['auto_detected'].items():
                    if artist_name in names:
                        logger.info(f"找到自动检测画师: {artist_name} -> {folder}")
                        return artist_name, folder, True
        
        # 如果都没找到，但有有效的画师名，返回第一个画师名作为新画师
        for artist_name in artist_names:
            if artist_name and not any(k in artist_name for k in self.config['exclude_keywords']):
                folder_name = f"[{artist_name}]"
                return artist_name, folder_name, False
        
        logger.debug(f"未找到匹配画师，文件名: {filename}")
        return None

    def _find_artist_folder(self, filename: str) -> Optional[Tuple[str, str]]:
        """查找匹配的画师文件夹（为了保持向后兼容）"""
        result = self._find_artist_info(filename)
        if result:
            artist_name, folder_name, _ = result
            return artist_name, folder_name
        return None

    def move_file(self, source_path: Path, target_folder: Path):
        """移动文件到目标文件夹"""
        # 根据源文件的完整路径检测类别
        category = self._detect_category(source_path)
        
        # 确定目标路径
        if category == "一般":
            # 如果没有匹配到类别，直接放在画师文件夹下
            target_path = target_folder / source_path.name
        else:
            # 检查画师文件夹下是否存在对应类别的子文件夹
            possible_folders = []
            for folder in target_folder.iterdir():
                if folder.is_dir():
                    # 检查文件夹名是否包含类别关键词
                    for keyword in self.config['categories'].get(category, []):
                        if keyword.lower() in folder.name.lower():
                            possible_folders.append(folder)
                            break
            
            if possible_folders:
                # 如果找到匹配的文件夹，使用第一个匹配的文件夹
                target_path = possible_folders[0] / source_path.name
                logger.info(f'找到匹配的子文件夹: "{possible_folders[0].name}"')
            else:
                # 如果没有找到匹配的文件夹，放在根目录
                target_path = target_folder / source_path.name
                logger.info(f'未找到匹配的子文件夹，放在根目录')
        
        # 处理文件名冲突
        if target_path.exists():
            new_name = f"🆕{source_path.name}"
            target_path = target_path.parent / new_name
            logger.info(f'文件已存在，更名为 "{new_name}"')
        
        # 移动文件
        shutil.move(str(source_path), str(target_path))
        # 保留时间戳
        original_stat = os.stat(target_path)
        os.utime(target_path, (original_stat.st_atime, original_stat.st_mtime))
        
        # 记录日志
        logger.info(f'已移动: "{source_path.name}" -> "{target_path.relative_to(target_folder)}"')

    def process_files(self):
        """处理待分类文件"""
        supported_formats = {'.zip', '.rar', '.7z'}
        
        # 获取所有待处理文件
        files = list(Path(self.pending_dir).rglob("*"))
        target_files = [f for f in files if f.suffix.lower() in supported_formats]
        
        logger.info(f"开始处理 {len(target_files)} 个文件...")
        
        if self.intermediate_mode:
            # 中间模式：使用文本模式的识别算法
            # 创建临时的文本文件
            temp_txt = Path(self.pending_dir) / "temp_to_be_classified.txt"
            with open(temp_txt, 'w', encoding='utf-8') as f:
                for file_path in target_files:
                    f.write(f"{file_path.name}\n")
            
            # 使用文本模式处理
            result = self.process_to_be_classified(str(temp_txt))
            
            # 在输入路径下创建转移文件夹
            found_dir = Path(self.pending_dir) / "[01已找到画师]"
            found_dir.mkdir(exist_ok=True)
            
            # 移动文件
            moved_files = []
            
            # 处理已存在的画师
            for folder_name, files_list in result['artists']['existing_artists'].items():
                # 检查画师文件夹是否存在
                artist_folder = self.base_dir / folder_name
                if not artist_folder.exists():
                    logger.warning(f"画师文件夹不存在，跳过移动: {folder_name}")
                    continue

                # 如果启用了创建画师文件夹选项，创建对应的文件夹
                target_dir = found_dir
                if self.create_artist_folders:
                    artist_folder_in_found = found_dir / folder_name
                    artist_folder_in_found.mkdir(exist_ok=True)
                    target_dir = artist_folder_in_found
                    self.copy_folder_structure(artist_folder, artist_folder_in_found)
                for file_name in files_list:
                    source_path = Path(self.pending_dir) / file_name
                    if source_path.exists():
                        target_path = target_dir / file_name
                        shutil.move(str(source_path), str(target_path))
                        moved_files.append((file_name, folder_name))
                        if self.create_artist_folders:
                            logger.info(f"已移动到已存在画师文件夹: {file_name} -> {folder_name}")
                        else:
                            logger.info(f"已移动到中间文件夹: {file_name} -> {folder_name}")
            
            # 处理新画师（不创建文件夹，也不移动到中间文件夹）
            for folder_name, files_list in result['artists']['new_artists'].items():
                for file_name in files_list:
                    logger.info(f"未找到画师文件夹，跳过移动: {file_name} -> {folder_name}")
            
            # 删除临时文件
            temp_txt.unlink()
            
            # 显示汇总信息
            if moved_files:
                logger.info("已找到的文件汇总:")
                for file_name, folder in moved_files:
                    logger.info(f"  - {file_name} -> {folder}")
            
            # 保存分类结果
            output_yaml = Path(self.pending_dir) / "classified_result.yaml"
            self.save_classification_result(result, str(output_yaml))
            
        else:
            # 直接模式：移动到画师文件夹
            for i, file_path in enumerate(target_files, 1):
                logger.info(f"正在检查: {file_path.name} ({i}/{len(target_files)})")
                
                artist_info = self._find_artist_folder(file_path.name)
                if artist_info:
                    artist_name, folder_name = artist_info
                    target_folder = self.base_dir / folder_name
                    try:
                        self.move_file(file_path, target_folder)
                        logger.info(f"已移动到画师文件夹: {file_path.name} -> {folder_name}")
                    except Exception as e:
                        logger.error(f"移动文件失败: {file_path.name} - {str(e)}")
                else:
                    logger.warning(f"未找到匹配画师: {file_path.name}")

    def extract_artist_info_from_filename(self, filename: str) -> Dict[str, List[str]]:
        """从文件名中提取画师信息"""
        result = {
            'artists': [],
            'circles': [],
            'raw_name': filename
        }
        
        # 清理文件名
        name_str = filename
        for keyword in self.config['exclude_keywords']:
            name_str = name_str.replace(keyword, "")
        
        # 提取方括号中的内容
        pattern = r'\[([^\[\]]+)\]'
        matches = re.finditer(pattern, name_str)
        
        for match in matches:
            content = match.group(1).strip()
            if '(' in content:
                # 处理带括号的情况 - 社团(画师)格式
                circle_part = content.split('(')[0].strip()
                artist_part = content.split('(')[1].rstrip(')').strip()
                
                # 处理画师名（按顿号分割）
                artist_names = [n.strip() for n in artist_part.split('、')]
                result['artists'].extend(artist_names)
                
                # 处理社团名（按顿号分割）
                circle_names = [n.strip() for n in circle_part.split('、')]
                result['circles'].extend(circle_names)
            else:
                # 没有括号的情况，假定为画师名
                result['artists'].append(content)
        
        # 过滤无效名称
        result['artists'] = [name for name in result['artists'] 
                           if name and not any(k in name for k in self.config['exclude_keywords'])]
        result['circles'] = [name for name in result['circles'] 
                           if name and not any(k in name for k in self.config['exclude_keywords'])]
        
        return result

    def process_to_be_classified(self, txt_path: str) -> Dict:
        """处理待分类的txt文件，生成分类结构"""
        logger.info(f"开始处理待分类文件: {txt_path}")
        
        if not os.path.exists(txt_path):
            raise FileNotFoundError(f"文件不存在: {txt_path}")
        
        # 读取txt文件
        with open(txt_path, 'r', encoding='utf-8') as f:
            filenames = [line.strip() for line in f if line.strip()]
        
        logger.info(f"读取到 {len(filenames)} 个文件名")
        
        # 初始化结果结构
        result = {
            'artists': {
                'existing_artists': {},  # 已存在的画师
                'new_artists': {},       # 新画师
                'user_defined': {}
            },
            'unclassified': [],
            'statistics': {
                'total_files': len(filenames),
                'classified_files': 0,
                'unclassified_files': 0,
                'existing_artists_count': 0,
                'new_artists_count': 0
            }
        }
        
        # 处理每个文件名
        for filename in filenames:
            artist_info = self._find_artist_info(filename)
            
            if artist_info:
                artist_name, folder_name, is_existing = artist_info
                # 根据是否为已存在画师选择目标字典
                target_dict = result['artists']['existing_artists'] if is_existing else result['artists']['new_artists']
                
                # 将文件名添加到对应的画师/社团文件夹下
                if folder_name not in target_dict:
                    target_dict[folder_name] = []
                target_dict[folder_name].append(filename)
                result['statistics']['classified_files'] += 1
            else:
                # 未能分类的文件
                result['unclassified'].append(filename)
                result['statistics']['unclassified_files'] += 1
        
        # 更新统计信息
        result['statistics']['existing_artists_count'] = len(result['artists']['existing_artists'])
        result['statistics']['new_artists_count'] = len(result['artists']['new_artists'])
        
        logger.info(f"分类完成: ")
        logger.info(f"- 总文件数: {result['statistics']['total_files']}")
        logger.info(f"- 已分类: {result['statistics']['classified_files']}")
        logger.info(f"- 未分类: {result['statistics']['unclassified_files']}")
        logger.info(f"- 已存在画师数: {result['statistics']['existing_artists_count']}")
        logger.info(f"- 新画师数: {result['statistics']['new_artists_count']}")
        
        return result

    def save_classification_result(self, result: Dict, output_path: str):
        """保存分类结果到yaml文件"""
        # 准备输出数据
        output_data = {
            'paths': self.config['paths'],
            'categories': self.config['categories'],
            'exclude_keywords': self.config['exclude_keywords'],
            'artists': result['artists']
        }
        
        # 添加未分类文件信息
        if result['unclassified']:
            output_data['unclassified'] = result['unclassified']
        
        # 添加统计信息
        output_data['statistics'] = result['statistics']
        
        # 保存到yaml文件
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(output_data, f, allow_unicode=True, sort_keys=False)
        
        logger.info(f"分类结果已保存到: {output_path}")
        # ...existing code...

    def copy_folder_structure(self, source_folder: Path, target_folder: Path):
        """
        复制源文件夹的一级子文件夹结构到目标文件夹
        
        Args:
            source_folder: 源文件夹路径
            target_folder: 目标文件夹路径
        """
        if not source_folder.exists() or not source_folder.is_dir():
            logger.warning(f"源文件夹不存在或不是文件夹: {source_folder}")
            return
        
        logger.info(f"正在复制文件夹结构: {source_folder} -> {target_folder}")
        
        # 确保目标文件夹存在
        target_folder.mkdir(exist_ok=True)
        
        # 只复制一级子文件夹
        subfolder_count = 0
        for item in source_folder.iterdir():
            if item.is_dir():
                new_folder = target_folder / item.name
                if not new_folder.exists():
                    new_folder.mkdir(exist_ok=True)
                    subfolder_count += 1
                    logger.debug(f"创建子文件夹: {new_folder.name}")
        
        logger.info(f"已复制 {subfolder_count} 个子文件夹结构")

