"""
系列提取核心功能模块
"""

import os
import re
import shutil
import logging
import threading
from typing import Optional
import difflib
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
# 可选依赖：rapidfuzz 与 diff_match_patch（缺失时回退到内置算法）
try:
    from rapidfuzz import fuzz, process  # type: ignore
except Exception:  # pragma: no cover
    class _FuzzFallback:
        @staticmethod
        def ratio(a, b):
            return int(difflib.SequenceMatcher(None, a, b).ratio() * 100)

        partial_ratio = ratio
        token_sort_ratio = ratio

    fuzz = _FuzzFallback()  # type: ignore
    process = None  # type: ignore

try:
    from diff_match_patch import diff_match_patch  # type: ignore
except Exception:  # pragma: no cover
    class diff_match_patch:  # minimal stub
        pass

from .utils import (
    normalize_chinese,
    is_archive,
    is_supported_file,
    is_series_blacklisted,
    SERIES_PREFIXES,
    setup_logger,
    load_seriex_config,
)

logger = setup_logger('seriex')

# 相似度配置
SIMILARITY_CONFIG = {
    'THRESHOLD': 75,  # 基本相似度阈值
    'LENGTH_DIFF_MAX': 0.3,  # 长度差异最大值
    'RATIO_THRESHOLD': 75,  # 完全匹配阈值
    'PARTIAL_THRESHOLD': 85,  # 部分匹配阈值
    'TOKEN_THRESHOLD': 80,  # 标记匹配阈值
}

# 已知系列名称缓存（来自配置目录的一级子目录名）
_KNOWN_SERIES_SET: set[str] = set()
_PROCESSED_DIRS: set[str] = set()
_LOAD_LOCK = threading.Lock()
_RUNTIME_KNOWN_SERIES_DIRS: list[str] = []  # 运行时覆盖用（CLI/外部注入）

def _series_in_known_set(series_name: str) -> bool:
    try:
        if not series_name:
            return False
        base = series_name
        for pfx in SERIES_PREFIXES:
            if base.startswith(pfx):
                base = base[len(pfx):]
                break
        base = base.strip()
        return base in _KNOWN_SERIES_SET
    except Exception:
        return False

def _load_known_series_from_dirs(dirs: list[str]):
    """从配置的目录收集一级子目录名称，填充 _KNOWN_SERIES_SET；可重复合并。"""
    with _LOAD_LOCK:
        for root in dirs:
            try:
                if not root:
                    continue
                root = os.path.abspath(root)
                if root in _PROCESSED_DIRS:
                    continue
                if not os.path.isdir(root):
                    _PROCESSED_DIRS.add(root)
                    continue
                for name in os.listdir(root):
                    full = os.path.join(root, name)
                    if not os.path.isdir(full):
                        continue
                    # 剥离可能存在的系列前缀
                    base = name
                    for pfx in SERIES_PREFIXES:
                        if base.startswith(pfx):
                            base = base[len(pfx):]
                            break
                    base = base.strip()
                    if base:
                        _KNOWN_SERIES_SET.add(base)
                _PROCESSED_DIRS.add(root)
            except Exception:
                # 忽略单个目录读取失败
                _PROCESSED_DIRS.add(root)
                continue

def calculate_similarity(str1, str2):
    """计算两个字符串的相似度"""
    # 标准化中文（转换为简体）后再比较
    str1 = normalize_chinese(str1)
    str2 = normalize_chinese(str2)
    
    ratio = fuzz.ratio(str1.lower(), str2.lower())
    partial = fuzz.partial_ratio(str1.lower(), str2.lower())
    token = fuzz.token_sort_ratio(str1.lower(), str2.lower())
    
    max_similarity = max(ratio, partial, token)
    if max_similarity >= SIMILARITY_CONFIG['THRESHOLD']:
        logger.info(f"相似度: {max_similarity}%")
    return max_similarity

def is_in_series_folder(file_path):
    """检查文件是否已经在系列文件夹内"""
    parent_dir = os.path.dirname(file_path)
    parent_name = os.path.basename(parent_dir)
    
    # 检查是否有系列标记
    for prefix in SERIES_PREFIXES:
        if parent_name.startswith(prefix):
            # 提取系列名称并重新用 get_series_key 处理
            series_name = parent_name[len(prefix):]  # 去掉前缀
            parent_key = get_series_key(series_name)
            file_key = get_series_key(os.path.basename(file_path))
            return parent_key == file_key
    
    # 如果父目录名称是文件名的一部分（去除数字和括号后），则认为已在系列文件夹内
    parent_key = get_series_key(parent_name)
    file_key = get_series_key(os.path.basename(file_path))
    
    if parent_key and parent_key in file_key:
        return True
    return False

def is_similar_to_existing_folder(dir_path, series_name):
    """检查是否存在相似的文件夹名称"""
    try:
        existing_folders = [d for d in os.listdir(dir_path) 
                          if os.path.isdir(os.path.join(dir_path, d))]
    except Exception as e:
        logger.error(f"读取目录失败: {dir_path}")
        return False
        
    series_key = get_series_key(series_name)
    
    for folder in existing_folders:
        # 检查所有支持的系列前缀
        is_series_folder = False
        folder_name = folder
        for prefix in SERIES_PREFIXES:
            if folder.startswith(prefix):
                # 对已有的系列文件夹使用相同的处理标准
                folder_name = folder[len(prefix):]  # 去掉前缀
                is_series_folder = True
                break
        
        if is_series_folder:
            folder_key = get_series_key(folder_name)
            
            # 如果系列键完全相同，直接返回True
            if series_key == folder_key:
                return True
            
            # 否则计算相似度
            similarity = calculate_similarity(series_key, folder_key)
            if similarity >= SIMILARITY_CONFIG['THRESHOLD']:
                return True
        else:
            # 对非系列文件夹使用原有的相似度检查
            similarity = calculate_similarity(series_name, folder)
            if similarity >= SIMILARITY_CONFIG['THRESHOLD']:
                return True
    return False

def get_base_filename(filename):
    """获取去除所有标签后的基本文件名"""
    # 去掉扩展名
    name = os.path.splitext(filename)[0]
    
    # 去除所有方括号及其内容
    name = re.sub(r'\[[^\]]*\]', '', name)
    # 去除所有圆括号及其内容
    name = re.sub(r'\([^)]*\)', '', name)
    # 去除所有空格和标点
    name = re.sub(r'[\s!！?？_~～]+', '', name)
    # 标准化中文（转换为简体）
    name = normalize_chinese(name)
    
    return name

def is_essentially_same_file(file1, file2):
    """检查两个文件是否本质上是同一个文件（只是标签不同）"""
    # 获取文件名（不含路径和扩展名）
    name1 = os.path.splitext(os.path.basename(file1))[0]
    name2 = os.path.splitext(os.path.basename(file2))[0]
    
    # 如果原始文件名完全相同，则认为是同一个文件
    if name1 == name2:
        return True
        
    # 去除所有标签、空格和标点
    base1 = re.sub(r'\[[^\]]*\]|\([^)]*\)', '', name1)  # 去除标签
    base2 = re.sub(r'\[[^\]]*\]|\([^)]*\)', '', name2)  # 去除标签
    
    # 去除所有空格和标点
    base1 = re.sub(r'[\s]+', '', base1).lower()
    base2 = re.sub(r'[\s]+', '', base2).lower()
    
    # 标准化中文（转换为简体）
    base1 = normalize_chinese(base1)
    base2 = normalize_chinese(base2)
    
    # 完全相同的基础名称才认为是同一个文件
    return base1 == base2

def preprocess_filename(filename):
    """预处理文件名"""
    # 获取文件名（不含路径）
    name = os.path.basename(filename)
    # 去除扩展名
    name = name.rsplit('.', 1)[0]
    
    # 检查是否有系列标记前缀，如果有则去除
    for prefix in SERIES_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
            
    # 去除方括号内容
    name = re.sub(r'\[.*?\]', '', name)
    # 去除圆括号内容
    name = re.sub(r'\(.*?\)', '', name)
    # 去除多余空格
    name = ' '.join(name.split())
    return name

def get_series_key(filename):
    """获取用于系列比较的键值"""
    logger.info(f"处理文件: {filename}")
    
    # 创建一个虚拟的对比组，包含当前文件和自身的副本
    # 这样可以利用 find_series_groups 的逻辑来提取系列名称
    test_group = [filename, filename]
    series_groups = find_series_groups(test_group)
    
    # 如果能找到系列名称，使用它
    if series_groups:
        series_name = next(iter(series_groups.keys()))
        logger.info(f"找到系列名称: {series_name}")
        return series_name
    
    # 如果找不到系列名称，退回到基本的预处理
    name = preprocess_filename(filename)
    name = normalize_chinese(name)
    
    logger.info(f"使用预处理结果: {name}")
    
    return name.strip()

def get_keywords(name):
    """将文件名分割为关键词列表"""
    return name.strip().split()

def find_longest_common_keywords(keywords1, keywords2):
    """找出两个关键词列表中最长的连续公共部分"""
    matcher = difflib.SequenceMatcher(None, keywords1, keywords2)
    match = matcher.find_longest_match(0, len(keywords1), 0, len(keywords2))
    return keywords1[match.a:match.a + match.size]

def validate_series_name(name):
    """验证和清理系列名称
    
    Args:
        name: 原始系列名称
        
    Returns:
        清理后的有效系列名称，如果无效则返回None
    """
    if not name or len(name) <= 1:
        return None
        
    # 标准化中文（转换为简体）
    name = normalize_chinese(name)
    
    # 去除末尾的特殊字符、数字和单字
    name = re.sub(r'[\s.．。·・+＋\-－—_＿\d]+$', '', name)  # 去除末尾的特殊符号和数字
    name = re.sub(r'[第章话集卷期篇季部册上中下前后完全][篇话集卷期章节部册全]*$', '', name)  # 去除末尾特殊词
    name = re.sub(r'(?i)vol\.?\s*\d*$', '', name)  # 去除末尾的vol.xxx
    name = re.sub(r'(?i)volume\s*\d*$', '', name)  # 去除末尾的volume xxx
    name = re.sub(r'(?i)part\s*\d*$', '', name)  # 去除末尾的part xxx
    name = name.strip()
    
    # 检查是否包含comic关键词
    if re.search(r'(?i)comic', name):
        return None
    
    # 检查是否只包含3个或更少的单字母
    words = name.split()
    if all(len(word) <= 1 for word in words) and len(''.join(words)) <= 3:
        return None
    
    # 最终检查：结果必须长度大于1且不能以单字结尾
    if not name or len(name) <= 1 or (len(name) > 0 and len(name.split()[-1]) <= 1):
        return None
        
    return name

def extract_keywords(filename):
    """从文件名中提取关键词"""
    # 去掉扩展名和方括号内容
    name = get_base_filename(filename)
    
    # 使用多种分隔符分割文件名
    separators = r'[\s]+'
    keywords = []
    
    # 分割前先去除其他方括号和圆括号的内容
    name = re.sub(r'\[[^\]]*\]|\([^)]*\)', ' ', name)
    
    # 分割并过滤空字符串
    parts = [p.strip() for p in re.split(separators, name) if p.strip()]
    
    # 对于每个部分，如果长度大于1，则添加到关键词列表
    for part in parts:
        if len(part) > 1:  # 忽略单个字符
            keywords.append(part)
    
    return keywords

def find_series_groups(filenames):
    """查找属于同一系列的文件组，使用三阶段匹配策略（含已知系列优先命中）"""
    # 预处理所有文件名
    processed_names = {f: preprocess_filename(f) for f in filenames}
    processed_keywords = {f: get_keywords(processed_names[f]) for f in filenames}
    # 为比较创建简体版本
    simplified_names = {f: normalize_chinese(n) for f, n in processed_names.items()}
    simplified_keywords = {f: [normalize_chinese(k) for k in kws] for f, kws in processed_keywords.items()}
    
    # 存储系列分组
    series_groups = defaultdict(list)
    # 待处理的文件集合
    remaining_files = set(filenames)
    # 记录已匹配的文件
    matched_files = set()
    
    # 预处理阶段：检查已标记的系列
    logger.info("预处理阶段：检查已标记的系列")
    
    for file_path in list(remaining_files):
        if file_path in matched_files:
            continue
            
        file_name = os.path.basename(file_path)
        for prefix in SERIES_PREFIXES:
            if file_name.startswith(prefix):
                # 提取系列名
                series_name = file_name[len(prefix):]
                # 去除可能的其他标记
                series_name = re.sub(r'\[.*?\]|\(.*?\)', '', series_name)
                series_name = series_name.strip()
                if series_name:
                    series_groups[series_name].append(file_path)
                    matched_files.add(file_path)
                    remaining_files.remove(file_path)
                    logger.info(f"预处理阶段：文件 '{os.path.basename(file_path)}' 已标记为系列 '{series_name}'")
                break
    
    # 优先阶段：根据配置的“已知系列名”直接命中（当文件名包含该系列名时）
    logger.info("优先阶段：准备加载已知系列目录配置...")
    try:
        # 优先使用运行时注入的目录，其次读取配置
        runtime_dirs = list(_RUNTIME_KNOWN_SERIES_DIRS)
        if runtime_dirs:
            _load_known_series_from_dirs(runtime_dirs)
        else:
            from .utils import load_seriex_config as _load_cfg  # 局部导入避免循环
            cfg = _load_cfg(None)
            known_dirs = cfg.get("known_series_dirs", []) if isinstance(cfg, dict) else []
            if isinstance(known_dirs, list) and known_dirs:
                _load_known_series_from_dirs(known_dirs)
    except Exception:
        pass

    logger.info(f"优先阶段：已知系列名数量={len(_KNOWN_SERIES_SET)}，待处理文件数={len(remaining_files)}")

    if _KNOWN_SERIES_SET and remaining_files:
        logger.info("优先阶段：匹配已知系列名（来自配置目录/运行时）")
        matched_by_known = defaultdict(list)
        known_norm_pairs: list[tuple[str, str]] = []  # (norm_no_space_lower, original)
        for s in _KNOWN_SERIES_SET:
            s_norm = normalize_chinese(s)
            s_norm = re.sub(r"\s+", "", s_norm)
            if s_norm:
                known_norm_pairs.append((s_norm.lower(), s))
        # 优先匹配更长的系列名以避免被较短前缀提前命中
        known_norm_pairs.sort(key=lambda x: len(x[0]), reverse=True)
        for file in list(remaining_files):
            # 使用原始文件名（不移除方括号/圆括号内容），仅去扩展名
            raw_name = os.path.basename(file)
            raw_name = raw_name.rsplit('.', 1)[0]
            base_name = normalize_chinese(raw_name)
            base_name_no_space = re.sub(r"\s+", "", base_name).lower()
            hit = None
            for s_norm, s_orig in known_norm_pairs:
                if s_norm and s_norm in base_name_no_space:
                    hit = s_orig
                    break
            if hit:
                matched_by_known[hit].append(file)
                matched_files.add(file)
                remaining_files.remove(file)
                logger.info(f"优先阶段：文件 '{os.path.basename(file)}' 命中已知系列 '{hit}'（包含系列名）")
        # 是否允许已知系列单文件成组
        try:
            from .utils import load_seriex_config as _load_cfg
            _cfg = _load_cfg(None) or {}
            allow_single = bool(_cfg.get("known_series_allow_single", True))
        except Exception:
            allow_single = True
        for series_name, files in matched_by_known.items():
            if len(files) > 1 or (allow_single and len(files) == 1):
                series_groups[series_name].extend(files)
                logger.info(f"优先阶段：将 {len(files)} 个文件加入已知系列 '{series_name}'")
    else:
        # 更友好的提示，帮助定位配置问题
        try:
            from .utils import load_seriex_config as _load_cfg
            cfg = _load_cfg(None)
            known_dirs = cfg.get("known_series_dirs", []) if isinstance(cfg, dict) else []
            has_runtime = bool(_RUNTIME_KNOWN_SERIES_DIRS)
            if not known_dirs and not has_runtime:
                logger.info("优先阶段：未配置已知系列目录，跳过")
            elif known_dirs or has_runtime:
                # 已配置但未加载到任何系列名
                logger.info("优先阶段：已配置已知系列目录但未发现可用的系列名，跳过")
        except Exception:
            pass

    # 第一阶段：风格匹配（关键词匹配）
    logger.info("第一阶段：风格匹配（关键词匹配）")
    
    while remaining_files:
        best_length = 0
        best_common = None
        best_pair = None
        best_series_name = None
        
        # 对剩余文件进行两两比较
        for file1 in remaining_files:
            if file1 in matched_files:
                continue
                
            keywords1 = simplified_keywords[file1]  # 使用简体版本比较
            base_name1 = get_base_filename(os.path.basename(file1))
            
            for file2 in remaining_files - {file1}:
                if file2 in matched_files:
                    continue
                    
                # 检查基础名是否完全相同
                base_name2 = get_base_filename(os.path.basename(file2))
                if base_name1 == base_name2:
                    continue  # 如果基础名完全相同,跳过这对文件
                    
                keywords2 = simplified_keywords[file2]  # 使用简体版本比较
                common = find_longest_common_keywords(keywords1, keywords2)
                
                if common and len(common) > best_length:
                    # 验证系列名称
                    series_name = validate_series_name(' '.join(common))
                    if series_name:
                        best_length = len(common)
                        best_common = common
                        best_pair = (file1, file2)
                        best_series_name = series_name
        
        if best_pair and best_series_name:
            matched_files_this_round = set(best_pair)
            base_name1 = get_base_filename(os.path.basename(best_pair[0]))
            
            for other_file in remaining_files - matched_files_this_round - matched_files:
                # 检查基础名是否与第一个文件相同
                other_base_name = get_base_filename(os.path.basename(other_file))
                if base_name1 == other_base_name:
                    continue  # 如果基础名相同,跳过这个文件
                    
                other_keywords = simplified_keywords[other_file]  # 使用简体版本比较
                common = find_longest_common_keywords(simplified_keywords[best_pair[0]], other_keywords)
                if common == best_common:
                    matched_files_this_round.add(other_file)
            
            # 使用最佳系列名
            series_groups[best_series_name].extend(matched_files_this_round)
            remaining_files -= matched_files_this_round
            matched_files.update(matched_files_this_round)
            
            logger.info(f"第一阶段：通过关键词匹配找到系列 '{best_series_name}'")
            for file_path in matched_files_this_round:
                logger.info(f"  └─ {os.path.basename(file_path)}")
        else:
            break  # 没有找到匹配，进入第二阶段
    
    # 第二阶段：完全基础名匹配
    if remaining_files:
        logger.info("第二阶段：完全基础名匹配")
        
        # 获取所有已存在的系列名
        existing_series = list(series_groups.keys())
        
        # 从目录中获取已有的系列文件夹名称
        dir_path = os.path.dirname(list(remaining_files)[0])  # 获取第一个文件的目录路径
        try:
            for folder_name in os.listdir(dir_path):
                if os.path.isdir(os.path.join(dir_path, folder_name)):
                    # 检查是否有系列标记
                    for prefix in SERIES_PREFIXES:
                        if folder_name.startswith(prefix):
                            series_name = folder_name[len(prefix):]  # 去掉前缀
                            if series_name not in existing_series:
                                existing_series.append(series_name)
                                logger.info(f"第二阶段：从目录中找到已有系列 '{series_name}'")
                            break
        except Exception:
            pass  # 如果读取目录失败，仅使用已有的系列名
        
        # 检查剩余文件是否包含已有系列名
        matched_files_by_series = defaultdict(list)
        for file in list(remaining_files):
            if file in matched_files:
                continue
                
            base_name = simplified_names[file]  # 使用简体版本比较
            base_name_no_space = re.sub(r'\s+', '', base_name)
            for series_name in existing_series:
                series_base = normalize_chinese(series_name)  # 只在比较时转换为简体
                series_base_no_space = re.sub(r'\s+', '', series_base)
                # 只要文件名中包含系列名就匹配
                if series_base_no_space in base_name_no_space:
                    # 检查是否有基础名相同的文件已经在这个系列中
                    base_name_current = get_base_filename(os.path.basename(file))
                    has_same_base = False
                    for existing_file in matched_files_by_series[series_name]:
                        if get_base_filename(os.path.basename(existing_file)) == base_name_current:
                            has_same_base = True
                            break
                    
                    if not has_same_base:
                        matched_files_by_series[series_name].append(file)  # 使用原始系列名
                        matched_files.add(file)
                        remaining_files.remove(file)
                        logger.info(f"第二阶段：文件 '{os.path.basename(file)}' 匹配到已有系列 '{series_name}'（包含系列名）")
                    break
        
        # 将匹配的文件添加到对应的系列组
        for series_name, files in matched_files_by_series.items():
            series_groups[series_name].extend(files)
            logger.info(f"第二阶段：将 {len(files)} 个文件添加到系列 '{series_name}'")
            for file_path in files:
                logger.info(f"  └─ {os.path.basename(file_path)}")
    
    # 第三阶段：最长公共子串匹配
    if remaining_files:
        logger.info("第三阶段：最长公共子串匹配")
            
        while remaining_files:
            best_ratio = 0
            best_pair = None
            best_common = None
            original_form = None  # 保存原始大小写形式
            
            # 对剩余文件进行两两比较
            for file1 in remaining_files:
                if file1 in matched_files:
                    continue
                    
                base1 = simplified_names[file1]  # 使用简体版本比较
                base1_lower = base1.lower()
                original1 = processed_names[file1]  # 保存原始形式
                base_name1 = get_base_filename(os.path.basename(file1))
                
                for file2 in remaining_files - {file1}:
                    if file2 in matched_files:
                        continue
                        
                    # 检查基础名是否完全相同
                    base_name2 = get_base_filename(os.path.basename(file2))
                    if base_name1 == base_name2:
                        continue  # 如果基础名完全相同,跳过这对文件
                        
                    base2 = simplified_names[file2]  # 使用简体版本比较
                    base2_lower = base2.lower()
                    
                    # 使用小写形式进行比较
                    matcher = difflib.SequenceMatcher(None, base1_lower, base2_lower)
                    ratio = matcher.ratio()
                    if ratio > best_ratio and ratio > 0.6:
                        best_ratio = ratio
                        best_pair = (file1, file2)
                        match = matcher.find_longest_match(0, len(base1_lower), 0, len(base2_lower))
                        best_common = base1_lower[match.a:match.a + match.size]
                        # 保存原始形式
                        original_form = original1[match.a:match.a + match.size]
            
            if best_pair and best_common and len(best_common.strip()) > 1:
                matched_files_this_round = set(best_pair)
                base_name1 = get_base_filename(os.path.basename(best_pair[0]))
                
                for other_file in remaining_files - matched_files_this_round - matched_files:
                    # 检查基础名是否与第一个文件相同
                    other_base_name = get_base_filename(os.path.basename(other_file))
                    if base_name1 == other_base_name:
                        continue  # 如果基础名相同,跳过这个文件
                        
                    other_base = simplified_names[other_file].lower()  # 使用简体小写版本比较
                    if best_common in other_base:
                        matched_files_this_round.add(other_file)
                
                # 使用原始形式作为系列名
                series_name = validate_series_name(original_form)
                if series_name:
                    series_groups[series_name].extend(matched_files_this_round)
                    remaining_files -= matched_files_this_round
                    matched_files.update(matched_files_this_round)
                    logger.info(f"第三阶段：通过公共子串匹配找到系列 '{series_name}'")
                    logger.info(f"  └─ 公共子串：'{best_common}' (相似度: {best_ratio:.2%})")
                    for file_path in matched_files_this_round:
                        logger.info(f"  └─ 文件 '{os.path.basename(file_path)}'")
                else:
                    remaining_files.remove(best_pair[0])
                    matched_files.add(best_pair[0])
            else:
                break
    
    if remaining_files:
        logger.warning(f"还有 {len(remaining_files)} 个文件未能匹配到任何系列")
    
    return dict(series_groups)

def update_series_folder_name(old_path, creation_prefix: str):
    """更新系列文件夹名称为最新标准"""
    try:
        dir_name = os.path.basename(old_path)
        is_series = False
        prefix_used = None
        
        # 检查是否是系列文件夹
        for prefix in SERIES_PREFIXES:
            if dir_name.startswith(prefix):
                is_series = True
                prefix_used = prefix
                break
                
        if not is_series:
            return False
            
        # 提取原始系列名
        old_series_name = dir_name[len(prefix_used):]
        # 使用新标准处理系列名
        new_series_name = get_series_key(old_series_name)

        if not new_series_name or new_series_name == old_series_name:
            return False

        # 创建新路径（使用配置的系列标记）
        new_prefix = creation_prefix or ""
        new_path = os.path.join(os.path.dirname(old_path), f'{new_prefix}{new_series_name}')

        # 如果新路径已存在，检查是否为不同路径
        if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(old_path):
            return False

        # 重命名文件夹
        os.rename(old_path, new_path)
        return True
        
    except Exception as e:
        logger.error(f"更新系列文件夹名称失败 {old_path}: {str(e)}")
        return False

def update_all_series_folders(directory_path, creation_prefix: str):
    """更新目录下所有的系列文件夹名称"""
    try:
        updated_count = 0
        for root, dirs, _ in os.walk(directory_path):
            for dir_name in dirs:
                # 任何已知前缀的目录都纳入更新判断
                if any(dir_name.startswith(pfx) for pfx in SERIES_PREFIXES):
                    full_path = os.path.join(root, dir_name)
                    if update_series_folder_name(full_path, creation_prefix):
                        updated_count += 1
        
        if updated_count > 0:
            logger.info(f"更新了 {updated_count} 个系列文件夹名称")
            
        return updated_count
        
    except Exception as e:
        logger.error(f"更新系列文件夹失败: {str(e)}")
        return 0

def move_corrupted_archive(file_path, base_path):
    """移动损坏的压缩包到损坏压缩包文件夹，保持原有目录结构"""
    try:
        # 获取相对路径
        rel_path = os.path.relpath(os.path.dirname(file_path), base_path)
        # 构建目标路径
        corrupted_base = os.path.join(base_path, "损坏压缩包")
        target_dir = os.path.join(corrupted_base, rel_path)
        
        # 确保目标目录存在
        os.makedirs(target_dir, exist_ok=True)
        
        # 构建目标文件路径
        target_path = os.path.join(target_dir, os.path.basename(file_path))
        
        # 如果目标路径已存在，添加数字后缀
        if os.path.exists(target_path):
            base, ext = os.path.splitext(target_path)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}"):
                counter += 1
            target_path = f"{base}_{counter}{ext}"
        
        # 移动文件
        shutil.move(file_path, target_path)
        logger.info(f"已移动损坏压缩包: {os.path.basename(file_path)} -> 损坏压缩包/{rel_path}")
            
    except Exception as e:
        logger.error(f"移动损坏压缩包失败 {file_path}: {str(e)}")

def _safe_move(src: str, dst: str, max_retries: int = 2) -> str:
    """更稳健的移动：
    - 若目标存在，自动添加 _1、_2… 后缀避免覆盖；
    - 若跨盘导致 os.rename/shutil.move 失败，退回 copy+remove；
    - 返回最终目标路径。
    """
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        base, ext = os.path.splitext(dst)
        candidate = dst
        idx = 1
        while os.path.exists(candidate):
            candidate = f"{base}_{idx}{ext}"
            idx += 1
        # 优先尝试 rename/move
        try:
            shutil.move(src, candidate)
            return candidate
        except Exception:
            # 跨设备等问题：copytree/copy2 回退
            for attempt in range(max_retries + 1):
                try:
                    shutil.copy2(src, candidate)
                    os.remove(src)
                    return candidate
                except Exception as ex:
                    if attempt >= max_retries:
                        raise ex
    except Exception as e:
        logger.error(f"移动失败: {os.path.basename(src)} -> {dst}: {e}")
        raise

def collect_items_for_series(directory_path, config, category_folders, dry_run: bool = False):
    """收集用于系列提取的候选文件（含压缩包与其它受支持格式）。

    返回 (items, corrupted)；完整性检测已移除，corrupted 始终为空。
    """
    base_level = len(Path(directory_path).parts)
    items: list[str] = []
    corrupted: list[str] = []
    
    for root, _, files in os.walk(directory_path):
        current_level = len(Path(root).parts)
        if current_level - base_level > 1:
            continue
            
        # 检查当前目录是否有系列标记或是损坏压缩包文件夹
        current_dir = os.path.basename(root)
        if current_dir.startswith('[#s]') or current_dir == "损坏压缩包":
            continue
            
        for file in files:
            # 收集受支持的文件
            if is_supported_file(file, config):
                file_path = os.path.join(root, file)
                # 检查文件名是否在系列提取黑名单中
                if is_series_blacklisted(file):
                    logger.warning(f"文件在系列提取黑名单中，跳过: {file}")
                    continue
                # 压缩包与其它受支持格式一并直接加入
                items.append(file_path)
                    
    return items, corrupted

def create_series_folders(directory_path, files, config, add_prefix: bool | None = None):
    """为同一系列的文件创建文件夹（文件可为压缩包/视频/自定义格式等）。

    返回值：summary 显示每个目录下创建的系列与移动的文件。
    { dir_path: { final_folder_name: [file_basename, ...] } }
    """
    dir_groups = defaultdict(list)
    summary: dict[str, dict[str, list[str]]] = {}
    use_prefix = add_prefix if add_prefix is not None else config.get("add_prefix", True)
    creation_prefix = config.get("prefix", "[#s]") if use_prefix else ""
    # 仅处理实际存在的受支持文件
    files = [f for f in files if os.path.isfile(f)]

    for fp in files:
        dir_path = os.path.dirname(fp)
        # 检查父目录是否有系列标记
        parent_name = os.path.basename(dir_path)
        is_series_dir = any(parent_name.startswith(prefix) for prefix in SERIES_PREFIXES)
        if is_series_dir:
            continue
        dir_groups[dir_path].append(fp)
    
    for dir_path, dir_archives in dir_groups.items():
        if len(dir_archives) <= 1:
            continue
        
        logger.info(f"找到 {len(dir_archives)} 个候选文件")
        
        series_groups = find_series_groups(dir_archives)
        
        if series_groups:
            logger.info(f"找到 {len(series_groups)} 个系列")
            
            # 移除“全部同系列直接跳过”的早退逻辑；仍然执行移动，按既有规则建目录
            
            # 创建一个字典来记录每个系列的文件夹路径
            series_folders = {}
            summary.setdefault(dir_path, {})
            
            # 首先创建所有需要的系列文件夹
            # 读取单文件允许策略
            allow_single = True
            try:
                allow_single = bool(load_seriex_config(None).get("known_series_allow_single", True))
            except Exception:
                allow_single = True

            for series_name, files in series_groups.items():
                # 跳过"其他"分类；单文件仅在命中参考系列名且允许时创建
                if series_name == "其他":
                    logger.warning(f"{len(files)} 个文件未能匹配到系列")
                    continue
                if len(files) <= 1 and not (allow_single and _series_in_known_set(series_name)):
                    logger.warning(f"系列 '{series_name}' 只有一个文件，且非参考系列或未启用单文件策略，跳过创建文件夹")
                    continue
                
                # 添加系列标记（使用配置前缀，或不添加）
                folder_name = f"{creation_prefix}{series_name.strip()}"
                series_folder = os.path.join(dir_path, folder_name)
                if not os.path.exists(series_folder):
                    os.makedirs(series_folder)
                    logger.info(f"创建系列文件夹: {folder_name}")
                series_folders[series_name] = series_folder
            
            # 然后移动每个系列的文件
            for series_name, folder_path in series_folders.items():
                files = series_groups[series_name]
                logger.info(f"开始移动系列 '{series_name}' 的文件...")
                moved_list: list[str] = []
                for file_path in files:
                    target_path = os.path.join(folder_path, os.path.basename(file_path))
                    try:
                        final_path = _safe_move(file_path, target_path)
                        logger.info(f"  └─ 移动: {os.path.basename(file_path)} -> {os.path.basename(final_path)}")
                        moved_list.append(os.path.basename(final_path))
                    except Exception:
                        logger.warning(f"移动失败，已跳过: {os.path.basename(file_path)}")
                # 记录汇总
                final_folder_name = os.path.basename(folder_path)
                if moved_list:
                    summary[dir_path].setdefault(final_folder_name, []).extend(moved_list)
            
        logger.info("系列提取完成")
        
        logger.info(f"目录处理完成: {dir_path}")
    return summary

def compute_series_plan(directory_path, files, config, add_prefix: bool | None = None):
    """计算系列文件夹与需要移动的文件（不产生任何副作用）。

    返回结构与 create_series_folders 相同的 summary，但不创建目录、不移动文件。
    """
    dir_groups = defaultdict(list)
    summary: dict[str, dict[str, list[str]]] = {}
    use_prefix = add_prefix if add_prefix is not None else config.get("add_prefix", True)
    creation_prefix = config.get("prefix", "[#s]") if use_prefix else ""
    files = [f for f in files if os.path.isfile(f)]

    for fp in files:
        dir_path = os.path.dirname(fp)
        parent_name = os.path.basename(dir_path)
        is_series_dir = any(parent_name.startswith(prefix) for prefix in SERIES_PREFIXES)
        if is_series_dir:
            continue
        dir_groups[dir_path].append(fp)

    for dir_path, dir_archives in dir_groups.items():
        if len(dir_archives) <= 1:
            continue

        series_groups = find_series_groups(dir_archives)
        if not series_groups:
            continue

        total_files = len(dir_archives)
        plan_for_dir: dict[str, list[str]] = {}

        # 读取单文件允许策略
        try:
            allow_single = bool(load_seriex_config(None).get("known_series_allow_single", True))
        except Exception:
            allow_single = True

        for series_name, files_in_series in series_groups.items():
            if series_name == "其他":
                continue
            if len(files_in_series) <= 1 and not (allow_single and _series_in_known_set(series_name)):
                continue
            if len(files_in_series) == total_files:
                # 全部文件同一系列，按原逻辑跳过创建子目录
                plan_for_dir = {}
                break
            folder_name = f"{creation_prefix}{series_name.strip()}"
            plan_for_dir[folder_name] = list(files_in_series)

        if plan_for_dir:
            summary[dir_path] = plan_for_dir

    return summary

class seriex:
    """系列提取器类，处理系列提取相关操作"""
    
    def __init__(self, similarity_config=None, config_path: Optional[str] = None, add_prefix: Optional[bool] = None):
        """初始化系列提取器
        
        Args:
            similarity_config: 相似度配置字典，如果提供则覆盖默认配置
        """
        self.logger = setup_logger('seriex')
        # 加载格式/行为配置（TOML）
        self.config = load_seriex_config(config_path)
        # 运行时是否添加系列前缀
        self.add_prefix = add_prefix if add_prefix is not None else self.config.get("add_prefix", True)
        # 将配置的创建前缀加入检测集合
        try:
            creation_prefix = self.config.get("prefix", "[#s]")
            if creation_prefix:
                SERIES_PREFIXES.add(creation_prefix)
        except Exception:
            pass
        # 最近一次运行的汇总/计划
        self.last_summary = {}
        self.last_plan = {}
        self.last_corrupted = []
        if similarity_config:
            SIMILARITY_CONFIG.update(similarity_config)
        # 预加载已知系列名（基于配置）
        try:
            dirs = self.config.get("known_series_dirs", [])
            if isinstance(dirs, list) and dirs:
                _load_known_series_from_dirs(dirs)
                # 同步到运行时变量，便于后续优先使用
                global _RUNTIME_KNOWN_SERIES_DIRS
                _RUNTIME_KNOWN_SERIES_DIRS = list(dirs)
        except Exception:
            pass

    def reload_known_series_dirs(self, dirs: list[str]):
        """运行时覆盖并重新加载已知系列目录。"""
        try:
            global _RUNTIME_KNOWN_SERIES_DIRS
            _RUNTIME_KNOWN_SERIES_DIRS = list(dirs)
            if dirs:
                _load_known_series_from_dirs(dirs)
        except Exception:
            pass
        
    def process_directory(self, directory_path):
        """处理指定目录，提取系列并整理到文件夹
        
        Args:
            directory_path: 要处理的目录路径
        
        Returns:
            bool: 处理是否成功
        """
        try:
            if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
                self.logger.error(f"目录不存在或不是有效目录: {directory_path}")
                return False
                
            # 更新旧的系列文件夹名称（仅在启用前缀时进行）
            if self.add_prefix:
                self.logger.info(f"检查并更新旧的系列文件夹名称...")
                creation_prefix = self.config.get("prefix", "[#s]")
                update_all_series_folders(directory_path, creation_prefix)
            
            # 收集用于系列提取的候选文件
            self.logger.info(f"开始查找可提取系列的文件（按配置扩展名）...")
            items, _ = collect_items_for_series(directory_path, self.config, [], dry_run=False)
            
            if not items:
                self.logger.info("没有找到可提取系列的文件")
                return True
            
            # 创建系列文件夹
            self.logger.info(f"在目录及其子文件夹下找到 {len(items)} 个有效文件")
            self.last_summary = create_series_folders(directory_path, items, self.config, add_prefix=self.add_prefix)
            
            self.logger.info(f"目录处理完成: {directory_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"处理目录时出错: {str(e)}")
            return False

    def prepare_directory(self, directory_path):
        """预处理：仅生成计划与摘要，不进行任何移动。"""
        if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
            self.logger.error(f"目录不存在或不是有效目录: {directory_path}")
            return {}
        # 不改名老目录以避免副作用
        items, corrupted = collect_items_for_series(directory_path, self.config, [], dry_run=True)
        self.last_corrupted = corrupted
        plan = compute_series_plan(directory_path, items, self.config, add_prefix=self.add_prefix)
        self.last_plan = plan
        return plan

    def apply_prepared_plan(self, directory_path):
        """执行上一次准备的计划，真正进行移动与目录创建，同时处理损坏包移动。"""
        if not self.last_plan:
            self.logger.info("没有可执行的计划")
            return {}
        # 移动损坏包
        if self.config.get("check_integrity", True) and self.last_corrupted:
            for path in self.last_corrupted:
                try:
                    move_corrupted_archive(path, directory_path)
                except Exception as e:
                    logger.error(f"移动损坏压缩包失败: {os.path.basename(path)}")

        # 执行计划：创建目录并移动
        summary: dict[str, dict[str, list[str]]] = {}
        for dir_path, folder_map in self.last_plan.items():
            summary.setdefault(dir_path, {})
            for folder_name, files in folder_map.items():
                series_folder = os.path.join(dir_path, folder_name)
                if not os.path.exists(series_folder):
                    os.makedirs(series_folder, exist_ok=True)
                    logger.info(f"创建系列文件夹: {folder_name}")
                moved_list: list[str] = []
                for file_path in files:
                    target_path = os.path.join(series_folder, os.path.basename(file_path))
                    try:
                        final_path = _safe_move(file_path, target_path)
                        logger.info(f"  └─ 移动: {os.path.basename(file_path)} -> {os.path.basename(final_path)}")
                        moved_list.append(os.path.basename(final_path))
                    except Exception:
                        logger.warning(f"移动失败，已跳过: {os.path.basename(file_path)}")
                if moved_list:
                    summary[dir_path].setdefault(folder_name, []).extend(moved_list)
        self.last_summary = summary
        return summary