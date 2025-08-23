import os
import re
import shutil
from datetime import datetime
from pathlib import Path
import argparse
import pyperclip
from collections import defaultdict
from typing import List, Set, Dict, Tuple
from colorama import init, Fore, Style
from opencc import OpenCC
import sys
import json

# from textual_logger import TextualLoggerManager
from loguru import logger
import os
import sys
from pathlib import Path
from datetime import datetime
from rich.prompt import Prompt, Confirm
from rich.console import Console

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
    )
    
    # 创建配置信息字典
    config_info = {
        'log_file': log_file,
    }
    
    logger.info(f"日志系统已初始化，应用名称: {app_name}")
    return logger, config_info

logger, config_info = setup_logger(app_name="samea", console_output=True)

# 初始化 colorama 和 OpenCC
# init()
cc_s2t = OpenCC('s2t')  # 简体到繁体
cc_t2s = OpenCC('t2s')  # 繁体到简体

def load_blacklist() -> Tuple[Set[str], List[str], Set[str]]:
    """从JSON文件加载黑名单配置"""
    blacklist_file = Path(__file__).parent / "blacklist.json"
    try:
        with open(blacklist_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        artist_blacklist = set(config.get('artist_blacklist', []))
        regex_patterns = config.get('regex_patterns', [])
        path_blacklist = set(config.get('path_blacklist', []))
        
        logger.info(f"✅ 成功加载黑名单配置: 画师关键词 {len(artist_blacklist)} 个, 正则模式 {len(regex_patterns)} 个, 路径黑名单 {len(path_blacklist)} 个")
        return artist_blacklist, regex_patterns, path_blacklist
        
    except Exception as e:
        logger.warning(f"⚠️ 加载黑名单配置失败，使用默认配置: {e}")
        # 返回默认配置
        return {
            '已找到', 'unknown', 'trash', '画集', '畫集', 'artbook', 'pixiv',
            '汉化', '漢化', '翻译', '翻訳', '中文', '中国翻译'
        }, ['v\\d+', '\\d{4}', '\\d{2}\\.\\d{2}'], {'[00画师分类]', 'trash', 'temp'}

# 加载黑名单配置
BLACKLIST_KEYWORDS, REGEX_PATTERNS, PATH_BLACKLIST = load_blacklist()

def save_blacklist(artist_blacklist: Set[str], regex_patterns: List[str], path_blacklist: Set[str]) -> bool:
    """保存黑名单配置到JSON文件"""
    blacklist_file = Path(__file__).parent / "blacklist.json"
    try:
        config = {
            "artist_blacklist": sorted(list(artist_blacklist)),
            "regex_patterns": regex_patterns,
            "path_blacklist": sorted(list(path_blacklist))
        }
        with open(blacklist_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ 黑名单配置已保存到: {blacklist_file}")
        return True
    except Exception as e:
        logger.error(f"❌ 保存黑名单配置失败: {e}")
        return False

def add_to_blacklist(keyword: str, blacklist_type: str = "artist") -> bool:
    """添加关键词到黑名单"""
    global BLACKLIST_KEYWORDS, REGEX_PATTERNS, PATH_BLACKLIST, _BLACKLIST_KEYWORDS_FULL
    
    keyword = keyword.strip()
    if not keyword:
        return False
    
    if blacklist_type == "artist":
        BLACKLIST_KEYWORDS.add(keyword)
        _BLACKLIST_KEYWORDS_FULL = preprocess_keywords(BLACKLIST_KEYWORDS)
        logger.info(f"✅ 已添加画师黑名单关键词: {keyword}")
    elif blacklist_type == "path":
        PATH_BLACKLIST.add(keyword)
        logger.info(f"✅ 已添加路径黑名单关键词: {keyword}")
    elif blacklist_type == "regex":
        REGEX_PATTERNS.append(keyword)
        logger.info(f"✅ 已添加正则黑名单模式: {keyword}")
    else:
        return False
    
    return save_blacklist(BLACKLIST_KEYWORDS, REGEX_PATTERNS, PATH_BLACKLIST)

def remove_from_blacklist(keyword: str, blacklist_type: str = "artist") -> bool:
    """从黑名单中移除关键词"""
    global BLACKLIST_KEYWORDS, REGEX_PATTERNS, PATH_BLACKLIST, _BLACKLIST_KEYWORDS_FULL
    
    keyword = keyword.strip()
    if not keyword:
        return False
    
    try:
        if blacklist_type == "artist" and keyword in BLACKLIST_KEYWORDS:
            BLACKLIST_KEYWORDS.remove(keyword)
            _BLACKLIST_KEYWORDS_FULL = preprocess_keywords(BLACKLIST_KEYWORDS)
            logger.info(f"✅ 已移除画师黑名单关键词: {keyword}")
        elif blacklist_type == "path" and keyword in PATH_BLACKLIST:
            PATH_BLACKLIST.remove(keyword)
            logger.info(f"✅ 已移除路径黑名单关键词: {keyword}")
        elif blacklist_type == "regex" and keyword in REGEX_PATTERNS:
            REGEX_PATTERNS.remove(keyword)
            logger.info(f"✅ 已移除正则黑名单模式: {keyword}")
        else:
            logger.warning(f"⚠️ 关键词不存在于黑名单中: {keyword}")
            return False
        
        return save_blacklist(BLACKLIST_KEYWORDS, REGEX_PATTERNS, PATH_BLACKLIST)
    except Exception as e:
        logger.error(f"❌ 移除黑名单关键词失败: {e}")
        return False

def preprocess_keywords(keywords: Set[str]) -> Set[str]:
    """预处理关键词集合，添加繁简体变体"""
    processed = set()
    for keyword in keywords:
        # 添加原始关键词（小写）
        processed.add(keyword.lower())
        # 添加繁体版本
        traditional = cc_s2t.convert(keyword)
        processed.add(traditional.lower())
        # 添加简体版本
        simplified = cc_t2s.convert(keyword)
        processed.add(simplified.lower())
    return processed

# 预处理黑名单关键词
_BLACKLIST_KEYWORDS_FULL = preprocess_keywords(BLACKLIST_KEYWORDS)

def is_explicit_blacklisted(name: str) -> bool:
    """显式黑名单判断（不含启发式规则）。
    仅依据：空、配置的正则、关键词集合。"""
    name_lower = name.lower().strip()
    if not name_lower:
        return True
    # 配置正则
    for pattern in REGEX_PATTERNS:
        try:
            if re.match(pattern, name_lower):
                return True
        except re.error:
            # 忽略无效正则
            continue
        # 仅当黑名单词作为整体或明显子词边界匹配时才过滤，避免 'laika' 被误杀如果某黑名单包含部分片段
        for keyword in _BLACKLIST_KEYWORDS_FULL:
            if not keyword:
                continue
            if name_lower == keyword:
                return True
            if keyword in name_lower:
                # 若关键词含 CJK（宽泛判断：任一字符在基本多文种之外或 in \u4e00-\u9fff），直接视为命中
                if any('\u4e00' <= ch <= '\u9fff' or ord(ch) > 0x3000 for ch in keyword):
                    # 单字 CJK（如 “汉” “漢”）只在完全相等时过滤，避免误杀含此字的正常名字
                    if len(keyword) == 1:
                        if name_lower == keyword:
                            return True
                    else:
                        return True
                # ASCII 关键词做边界检查，避免误伤
                idx = name_lower.find(keyword)
                before_ok = (idx == 0) or (not name_lower[idx-1].isalnum())
                after_pos = idx + len(keyword)
                after_ok = (after_pos == len(name_lower)) or (not name_lower[after_pos].isalnum())
                if before_ok and after_ok:
                    return True
    return False

def is_heuristically_invalid(name: str) -> bool:
    """更窄的启发式过滤：仅拒绝明显无意义 token。
    规则：
      1) 纯数字 (避免年份/日期)
      2) 长度 <=2 的纯字母/数字 (a, b1, cg 之类交给黑名单; 这里只做长度限制)
      3) 特定模式: v\d+, vol\d+, ch\d+, ep\d+ (早期/章节号)
    其余放行，避免误杀 'Laika', 'Caisan', 'kaim' 等。
    """
    name_lower = name.lower().strip()
    if not name_lower:
        return True
    if name_lower.isdigit():
        return True
    if re.fullmatch(r'[0-9a-zA-Z]{1,2}', name_lower):
        return True
    if re.fullmatch(r'(?:v|vol|ch|ep)\d{1,3}', name_lower):
        return True
    return False

def is_artist_name_blacklisted(name: str, *, allow_heuristic: bool = True) -> bool:
    """综合判断。
    allow_heuristic=True 时：显式 + 启发式 都过滤。
    allow_heuristic=False 时：仅使用显式黑名单（用于回退阶段放宽限制）。"""
    if is_explicit_blacklisted(name):
        return True
    if allow_heuristic and is_heuristically_invalid(name):
        return True
    return False

def find_balanced_brackets(text: str) -> List[Tuple[int, int, str]]:
    """
    找到所有配对的方括号及其内容
    返回: [(start_pos, end_pos, content), ...]
    """
    brackets = []
    stack = []
    i = 0
    
    while i < len(text):
        if text[i] == '[':
            stack.append(i)
        elif text[i] == ']' and stack:
            start = stack.pop()
            content = text[start+1:i]
            # 只保留内容不为空且不包含嵌套方括号的
            if content and '[' not in content and ']' not in content:
                brackets.append((start, i, content))
        i += 1
    
    return brackets

def extract_artist_info(filename: str) -> List[Tuple[str, str]]:
    """
    从文件名中提取画师信息，使用字符串匹配避免正则表达式问题
    返回格式: [(社团名, 画师名), ...]
    """
    artist_infos = []
    
    # 找到所有配对的方括号
    brackets = find_balanced_brackets(filename)
    bracket_contents = [content.strip() for _, _, content in brackets if content.strip()]
    
    logger.debug(f"🔍 找到配对方括号内容: {bracket_contents}")
    
    # 方法1: 优先匹配包含圆括号的格式 "社团名 (画师名)"
    for content in bracket_contents:
        # 检查是否包含圆括号
        paren_start = content.find('(')
        paren_end = content.rfind(')')
        
        if paren_start > 0 and paren_end > paren_start:
            group = content[:paren_start].strip()
            artist = content[paren_start+1:paren_end].strip()
            
            # 检查社团名和画师名是否都不在黑名单中
            if not is_artist_name_blacklisted(artist) and not is_artist_name_blacklisted(group):
                artist_infos.append((group, artist))
                logger.debug(f"✅ 提取到画师信息 (格式1): [{group} ({artist})]")
            elif not is_artist_name_blacklisted(artist):
                # 如果社团名在黑名单但画师名不在，只保留画师名
                artist_infos.append(('', artist))
                logger.debug(f"✅ 提取到画师信息 (格式1-简化): [{artist}] (社团名被过滤)")
            else:
                logger.debug(f"⏭️ 跳过黑名单画师 (格式1): [{group} ({artist})]")
    
    # 如果找到了标准格式的画师信息，优先返回这些
    if artist_infos:
        return artist_infos
    
    # 方法2: 查找相邻的方括号对
    brackets_with_pos = find_balanced_brackets(filename)
    for i in range(len(brackets_with_pos) - 1):
        curr_start, curr_end, curr_content = brackets_with_pos[i]
        next_start, next_end, next_content = brackets_with_pos[i + 1]
        
        # 检查两个方括号是否相邻（中间只有空格或没有字符）
        between_text = filename[curr_end + 1:next_start].strip()
        if len(between_text) == 0:  # 紧挨着的方括号
            curr_content = curr_content.strip()
            next_content = next_content.strip()
            
            # 检查是否都不在黑名单中
            curr_blacklisted = is_artist_name_blacklisted(curr_content)
            next_blacklisted = is_artist_name_blacklisted(next_content)
            
            if not next_blacklisted and not curr_blacklisted:
                # 都不在黑名单，第一个作为社团，第二个作为画师
                artist_infos.append((curr_content, next_content))
                logger.debug(f"✅ 提取到画师信息 (格式2): [{curr_content}][{next_content}]")
            elif not next_blacklisted:
                # 第一个在黑名单，第二个不在，只用第二个作为画师
                artist_infos.append(('', next_content))
                logger.debug(f"✅ 提取到画师信息 (格式2-第二个): [{next_content}]")
            elif not curr_blacklisted:
                # 第二个在黑名单，第一个不在，用第一个作为画师
                artist_infos.append(('', curr_content))
                logger.debug(f"✅ 提取到画师信息 (格式2-第一个): [{curr_content}]")
            else:
                logger.debug(f"⏭️ 跳过黑名单内容 (格式2): [{curr_content}][{next_content}]")
    
    # 如果找到了连续方括号格式的画师信息，返回这些
    if artist_infos:
        return artist_infos
    
    # 方法3: 处理独立的方括号内容（正常阶段）
    seen = set()
    for content in bracket_contents:
        if content in seen:
            continue
        seen.add(content)
        if not is_artist_name_blacklisted(content):
            artist_infos.append(('', content))
            logger.debug(f"✅ 提取到画师信息 (格式3): [{content}]")
        else:
            logger.debug(f"⏭️ 跳过内容 (格式3 初始阶段): [{content}]")

    # 回退阶段：如果仍未找到结果，尝试放宽启发式限制
    if not artist_infos and bracket_contents:
        # 情况1：只有一个方括号内容 -> 只要不在显式黑名单中就接受
        if len(bracket_contents) == 1:
            only_content = bracket_contents[0]
            # 单一内容：放宽启发式。如果是纯数字或短标签也允许；若仅被正则匹配阻挡也尝试放行。
            if not is_explicit_blacklisted(only_content) or only_content.isdigit():
                artist_infos.append(('', only_content))
                logger.debug(f"🔄 回退接受单一方括号内容(放宽启发式/数值豁免): [{only_content}]")
        else:
            # 情况2：多项内容，选择首个不在显式黑名单中的（忽略启发式）
            for content in bracket_contents:
                if not is_explicit_blacklisted(content):
                    artist_infos.append(('', content))
                    logger.debug(f"🔄 回退放宽启发式接受: [{content}]")
                    break
            # 如果依然找不到，保持空（不要再强行兜底），避免把纯噪声如 DL版 当成画师。

    # 移除“终极兜底”以避免过度放宽；保持严格策略。

    return artist_infos

def find_common_artists(files: List[str], min_occurrences: int = 2) -> Dict[str, List[str]]:
    """
    找出文件列表中重复出现的画师名
    返回: {画师名: [相关文件列表]}
    """
    artist_files = defaultdict(list)
    artist_occurrences = defaultdict(int)
    
    for file in files:
        artist_infos = extract_artist_info(file)
        for group, artist in artist_infos:
            key = f"{group}_{artist}" if group else artist
            artist_files[key].append(file)
            artist_occurrences[key] += 1
    
    # 只保留出现次数达到阈值的画师
    common_artists = {
        artist: files 
        for artist, files in artist_files.items() 
        if artist_occurrences[artist] >= min_occurrences
    }
    
    return common_artists

def is_path_blacklisted(path: str) -> bool:
    """检查路径是否在黑名单中"""
    path_lower = path.lower()
    return any(keyword.lower() in path_lower for keyword in PATH_BLACKLIST)

def clean_path(path: str) -> str:
    """去除路径前后空格和单双引号，并标准化分隔符"""
    return os.path.normpath(path.strip().strip('"').strip("'"))

def process_directory(directory: str, ignore_blacklist: bool = False, min_occurrences: int = 2, centralize: bool = False, debug: bool = False) -> None:
    """处理单个目录，并保存处理数据到json

    Args:
        directory: 待处理根目录
        ignore_blacklist: 是否忽略路径黑名单
        min_occurrences: 建立画师文件夹所需的最小文件数
        centralize: 是否集中收纳到 [00画师分类] 目录下。
            False 时：直接在当前目录下建立画师子目录 (默认行为)
            True  时：在目录下建立 [00画师分类] 作为总收纳目录
    """
    # 路径清理
    directory = clean_path(directory)
    # 检查目录本身是否在黑名单中
    if not ignore_blacklist and is_path_blacklisted(directory):
        logger.warning(f"⚠️ 跳过黑名单目录: {directory}")
        return
    # 决定画师分类基目录
    if centralize:
        artists_base_dir = os.path.join(directory, "[00画师分类]")
        try:
            os.makedirs(artists_base_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"❌ 创建画师分类目录失败: {str(e)}")
            return
        logger.info("📁 使用集中收纳模式: 文件将移动到 [00画师分类]/* 内")
    else:
        artists_base_dir = directory
        logger.info("📁 使用就地整理模式: 文件将直接移动到当前目录下新建的画师子目录内")
    # 收集所有压缩文件（跳过黑名单目录）
    all_files = []
    logger.info("🔍 正在扫描文件...")
    for root, _, files in os.walk(directory):
        if not ignore_blacklist and is_path_blacklisted(root):
            logger.info(f"⏭️ 跳过目录: {os.path.basename(root)}")
            continue
        for file in files:
            if file.lower().endswith(('.zip', '.rar', '.7z')):
                try:
                    if not ignore_blacklist and is_path_blacklisted(file):
                        logger.info(f"⏭️ 跳过文件: {file}")
                        continue
                    rel_path = os.path.relpath(os.path.join(root, file), directory)
                    all_files.append(rel_path)
                except Exception as e:
                    logger.warning(f"⚠️ 处理文件路径失败 {file}: {str(e)}")
                    continue
    logger.info(f"📊 发现 {len(all_files)} 个压缩文件")
    if not all_files:
        logger.warning(f"⚠️ 目录 {directory} 中未找到压缩文件")
        return
    logger.info("🔍 正在分析画师信息...")
    # 可选调试：逐文件展示解析
    if debug:
        for f in all_files:
            infos = extract_artist_info(os.path.basename(f))
            if infos:
                logger.debug(f"🐛DEBUG 提取 {f} => {infos}")
            else:
                logger.debug(f"🐛DEBUG 提取 {f} => 无有效画师信息")

    artist_groups = find_common_artists(all_files, min_occurrences=min_occurrences)
    if not artist_groups:
        logger.warning("⚠️ 未找到符合条件的画师")
        return
    # 记录处理结果
    process_result = {
        "base_dir": directory,
        "artists": [],
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    # 创建画师目录并移动文件
    for artist_key, files in artist_groups.items():
        artist_info = {
            "artist_key": artist_key,
            "files": files,
            "target_dir": None,
            # "success": 0,
            # "fail": 0,
            # "fail_detail": []
        }
        try:
            group, artist = artist_key.split('_') if '_' in artist_key else ('', artist_key)
            artist_name = f"[{group} ({artist})]" if group else f"[{artist}]"
            artist_dir = os.path.join(artists_base_dir, artist_name)
            artist_info["target_dir"] = artist_dir
            logger.info(f"🎨 处理画师: {artist_name}")
            logger.info(f"📊 找到 {len(files)} 个相关文件")
            try:
                os.makedirs(artist_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"❌ 创建画师目录失败 {artist_name}: {str(e)}")
                artist_info["fail"] = len(files)
                artist_info["fail_detail"] = [f"创建画师目录失败: {str(e)}"]
                process_result["artists"].append(artist_info)
                continue
            success_count = 0
            error_count = 0
            fail_detail = []
            for file in files:
                try:
                    src_path = os.path.join(directory, file)
                    if not os.path.exists(src_path):
                        logger.warning(f"⚠️ 源文件不存在: {file}")
                        error_count += 1
                        fail_detail.append(f"源文件不存在: {file}")
                        continue
                    dst_path = os.path.join(artist_dir, os.path.basename(file))
                    if os.path.exists(dst_path):
                        logger.warning(f"⚠️ 目标文件已存在: {os.path.basename(dst_path)}")
                        error_count += 1
                        fail_detail.append(f"目标文件已存在: {os.path.basename(dst_path)}")
                        continue
                    shutil.move(src_path, dst_path)
                    success_count += 1
                    if centralize:
                        logger.info(f"✅ 已移动: {file} -> [00画师分类]/{artist_name}/")
                    else:
                        logger.info(f"✅ 已移动: {file} -> {artist_name}/")
                except Exception as e:
                    error_count += 1
                    fail_detail.append(f"移动失败 {os.path.basename(file)}: {str(e)}")
                    logger.warning(f"⚠️ 移动失败 {os.path.basename(file)}: {str(e)}")
                    continue
            if success_count > 0 or error_count > 0:
                status = []
                if success_count > 0:
                    status.append(f"✅ 成功: {success_count}")
                if error_count > 0:
                    status.append(f"⚠️ 失败: {error_count}")
                logger.info(f"📊 {artist_name} 处理完成 - " + ", ".join(status))
            # artist_info["success"] = success_count 
            # artist_info["fail"] = error_count
            # artist_info["fail_detail"] = fail_detail
        except Exception as e:
            logger.error(f"⚠️ 处理画师 {artist_key} 时出错: {str(e)}")
            # artist_info["fail"] = len(files)
            # artist_info["fail_detail"] = [f"处理画师异常: {str(e)}"]
        process_result["artists"].append(artist_info)
    # 保存json
    log_dir = os.path.join(directory)
    os.makedirs(log_dir, exist_ok=True)
    json_path = os.path.join(log_dir, f"process_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(process_result, f, ensure_ascii=False, indent=2)
        logger.info(f"处理结果已保存到: {json_path}")
    except Exception as e:
        logger.error(f"❌ 保存处理结果到json失败: {e}")

def get_paths_from_clipboard():
    """从剪贴板读取多行路径"""
    try:
        clipboard_content = pyperclip.paste()
        if not clipboard_content:
            return []
        paths = [
            clean_path(path)
            for path in clipboard_content.splitlines() 
            if path.strip()
        ]
        valid_paths = [
            path for path in paths 
            if os.path.exists(path)
        ]
        if valid_paths:
            logger.info(f"📋 从剪贴板读取到 {len(valid_paths)} 个有效路径")
        else:
            logger.warning("⚠️ 剪贴板中没有有效路径")
        return valid_paths
    except Exception as e:
        logger.error(f"❌ 读取剪贴板时出错: {e}")
        return []

def manage_blacklist():
    """黑名单管理界面"""
    console = Console()
    
    while True:
        console.rule("[bold blue]黑名单管理")
        console.print("[cyan]当前黑名单统计:[/cyan]")
        console.print(f"  🎨 画师关键词: {len(BLACKLIST_KEYWORDS)} 个")
        console.print(f"  📁 路径关键词: {len(PATH_BLACKLIST)} 个")
        console.print(f"  📝 正则模式: {len(REGEX_PATTERNS)} 个")
        
        action = Prompt.ask(
            "请选择操作",
            choices=["view", "add", "remove", "back"],
            default="back"
        )
        
        if action == "back":
            break
        elif action == "view":
            view_type = Prompt.ask(
                "查看哪种黑名单",
                choices=["artist", "path", "regex"],
                default="artist"
            )
            if view_type == "artist":
                console.print("[green]画师黑名单关键词:[/green]")
                for i, keyword in enumerate(sorted(BLACKLIST_KEYWORDS), 1):
                    console.print(f"  {i:3d}. {keyword}")
            elif view_type == "path":
                console.print("[green]路径黑名单关键词:[/green]")
                for i, keyword in enumerate(sorted(PATH_BLACKLIST), 1):
                    console.print(f"  {i:3d}. {keyword}")
            elif view_type == "regex":
                console.print("[green]正则模式:[/green]")
                for i, pattern in enumerate(REGEX_PATTERNS, 1):
                    console.print(f"  {i:3d}. {pattern}")
        
        elif action == "add":
            add_type = Prompt.ask(
                "添加到哪种黑名单",
                choices=["artist", "path", "regex"],
                default="artist"
            )
            keyword = Prompt.ask("请输入要添加的关键词/模式")
            if keyword:
                if add_to_blacklist(keyword, add_type):
                    console.print(f"[green]✅ 成功添加: {keyword}[/green]")
                else:
                    console.print(f"[red]❌ 添加失败: {keyword}[/red]")
        
        elif action == "remove":
            remove_type = Prompt.ask(
                "从哪种黑名单移除",
                choices=["artist", "path", "regex"],
                default="artist"
            )
            keyword = Prompt.ask("请输入要移除的关键词/模式")
            if keyword:
                if remove_from_blacklist(keyword, remove_type):
                    console.print(f"[green]✅ 成功移除: {keyword}[/green]")
                else:
                    console.print(f"[red]❌ 移除失败: {keyword}[/red]")

def main():
    """主函数"""
    console = Console()
    
    # 检查是否有命令行参数
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description='寻找同画师的压缩包文件')
        parser.add_argument('-c', '--clipboard', action='store_true', help='从剪贴板读取路径')
        parser.add_argument('--ignore-blacklist', action='store_true', help='忽略路径黑名单')
        parser.add_argument('--path', help='要处理的路径')
        parser.add_argument('--min-occurrences', type=int, default=1, help='建立画师文件夹所需的最小文件数（如1则单文件也建文件夹）')
        parser.add_argument('--manage-blacklist', action='store_true', help='管理黑名单')
        parser.add_argument('--centralize', action='store_true', help='集中收纳到[00画师分类]目录 (默认否)')
        parser.add_argument('--debug', action='store_true', help='调试模式：输出每个文件的解析结果')
        args = parser.parse_args()

        if args.manage_blacklist:
            manage_blacklist()
            return
    else:
        # 交互式模式
        console.rule("[bold green]同画师压缩包分类工具")

        mode = Prompt.ask(
            "请选择模式",
            choices=["process", "blacklist"],
            default="process"
        )

        if mode == "blacklist":
            manage_blacklist()
            return

        console.rule("[bold green]参数设置")
        clipboard = Confirm.ask("是否从剪贴板读取路径?", default=True)
        ignore_blacklist = Confirm.ask("是否忽略路径黑名单?", default=False)
        min_occurrences = Prompt.ask("建立画师文件夹所需的最小文件数（如1则单文件也建文件夹）", default="1")
        path = Prompt.ask("请输入要处理的路径（可留空，回车跳过）", default="")
        centralize = Confirm.ask("是否集中收纳到 [00画师分类] 目录?", default=False)

        class Args:
            pass
        args = Args()
        args.clipboard = clipboard
        args.ignore_blacklist = ignore_blacklist
        args.path = path
        args.centralize = centralize
        try:
            args.min_occurrences = int(min_occurrences)
        except Exception:
            args.min_occurrences = 2
        args.debug = False
    
    # 处理路径
    paths = []
    if args.clipboard:
        paths.extend(get_paths_from_clipboard())
    elif args.path:
        paths.append(clean_path(args.path))
    else:
        console.print("[yellow]请输入要处理的路径（每行一个，输入空行结束）：[/yellow]")
        while True:
            try:
                line = input().strip()
                if not line:
                    break
                paths.append(clean_path(line))
            except (EOFError, KeyboardInterrupt):
                console.print("[red]用户取消输入[/red]")
                return
    
    if not paths:
        logger.error("❌ 未提供任何路径")
        return
    
    valid_paths = [path for path in paths if os.path.exists(path)]
    if not valid_paths:
        logger.error("❌ 没有有效的路径")
        return
    
    for path in valid_paths:
        logger.info(f"🚀 开始处理目录: {path}")
        process_directory(path, ignore_blacklist=args.ignore_blacklist, min_occurrences=args.min_occurrences, centralize=getattr(args, 'centralize', False), debug=getattr(args, 'debug', False))
        logger.info(f"✨ 目录处理完成: {path}")

if __name__ == "__main__":
    main()
