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

# 黑名单关键词
BLACKLIST_KEYWORDS = {
    '已找到',
    'unknown',  # 未知画师
    # 画集/图集相关
    'trash', '画集', '畫集', 'artbook', 'art book', 'art works', 'illustrations',
    '图集', '圖集', 'illust', 'collection',
    '杂图', '雜圖', '杂图合集', '雜圖合集',
    # 其他不需要处理的类型
    'pixiv', 'fanbox', 'gumroad', 'twitter',
    '待分类', '待處理', '待分類',
    '图包', '圖包',
    '图片', '圖片',
    'cg', 'CG',
    r'v\d+',  # v2, v3 等版本号
    # 常见标签
    'R18', 'COMIC', 'VOL', '汉化', '漢化', '中国翻訳',
    # 日期标记
    r'\d{4}', r'\d{2}\.\d{2}',
    # 其他通用标记
    'DL版', 'Digital', '無修正',
    # 翻译相关关键词
    '中国翻译', '中国翻訳', '中国語', '中国语',
    '中文', '中文翻译', '中文翻訳',
    '日語', '日语', '翻訳', '翻译',
    '汉化组', '漢化組', '汉化社', '漢化社',
    '汉化', '漢化', '翻译版', '翻訳版',
    '机翻', '機翻', '人工翻译', '人工翻訳',
    '中国', '中國', '日本語', '日本语'
    '汉化', '漢化',  # 汉化/漢化
    '翻译', '翻訳', '翻譯', # 翻译相关
    '中国翻译', '中国翻訳', '中国語','chinese','中文','中国', # 中文翻译
    '嵌字',  # 嵌字
    '掃圖', '掃', # 扫图相关
    '制作', '製作', # 制作相关
    '重嵌',  # 重新嵌入
    '个人', # 个人翻译
    '修正',  # 修正版本
    '去码',
    '日语社',
    '制作',
    '机翻',
    '赞助',
    '汉', '漢', # 汉字相关
    '数位', '未来数位', '新视界', # 汉化相关
    '出版', '青文出版', # 翻译相关
    '脸肿', '无毒', '空気系', '夢之行蹤', '萌幻鴿鄉', '绅士仓库', 'Lolipoi', '靴下','CE家族社',
    '不可视', '一匙咖啡豆', '无邪气', '洨五', '白杨', '瑞树',  # 常见汉化组名
    '汉化组', '漢化組', '汉化社', '漢化社', 'CE 家族社', 'CE 家族社',  # 常见后缀
    '个人汉化', '個人漢化'  # 个人汉化
}

# 添加路径黑名单关键词
PATH_BLACKLIST = {
    '[00画师分类]',  # 已经分类的画师目录
    '[00待分类]',    # 待分类目录
    '[00去图]',      # 去图目录
    '已找到',        # 杂项目录
    '[02COS]',       # COS目录
    'trash',         # 垃圾箱
    'temp',          # 临时目录
    '待处理',        # 待处理目录
    # '新建文件夹'     # 临时文件夹
}

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

def extract_artist_info(filename: str) -> List[Tuple[str, str]]:
    """
    从文件名中提取画师信息
    返回格式: [(社团名, 画师名), ...]
    """
    # 匹配[社团名 (画师名)]格式
    pattern1 = r'\[(.*?)\s*\((.*?)\)\]'
    matches1 = re.findall(pattern1, filename)
    if matches1:
        return [(group, artist) for group, artist in matches1]
    
    # 匹配所有方括号内容
    pattern2 = r'\[(.*?)\]'
    matches2 = re.findall(pattern2, filename)
    
    # 过滤黑名单关键词和特殊模式
    filtered_matches = []
    for match in matches2:
        match_lower = match.lower()
        
        # 跳过纯数字
        if match.isdigit():
            continue
            
        # 跳过日期格式 (YYYYMMDD)
        if re.match(r'^\d{8}$', match):
            continue
            
        # 跳过日期格式 (YYYYMM)
        if re.match(r'^\d{6}$', match):
            continue
            
        # 跳过类似[013]这样的短数字
        if re.match(r'^\d{1,3}$', match):
            continue
            
        # 跳过版本号格式
        if re.match(r'^v\d+$', match.lower()):
            continue
            
        # 跳过数字字母混合的短标记
        if re.match(r'^[0-9a-zA-Z]{1,6}$', match):
            continue
            
        # 跳过黑名单关键词
        if any(keyword in match_lower for keyword in _BLACKLIST_KEYWORDS_FULL):
            continue
            
        filtered_matches.append(('', match))
            
    return filtered_matches

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

def process_directory(directory: str, ignore_blacklist: bool = False, min_occurrences: int = 2) -> None:
    """处理单个目录，并保存处理数据到json"""
    # 路径清理
    directory = clean_path(directory)
    # 检查目录本身是否在黑名单中
    if not ignore_blacklist and is_path_blacklisted(directory):
        logger.warning(f"⚠️ 跳过黑名单目录: {directory}")
        return
    # 创建画师分类总目录
    artists_base_dir = os.path.join(directory, "[00画师分类]")
    try:
        os.makedirs(artists_base_dir, exist_ok=True)
    except Exception as e:
        logger.error(f"❌ 创建画师分类目录失败: {str(e)}")
        return
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
                    logger.info(f"✅ 已移动: {file} -> [00画师分类]/{artist_name}/")
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

def main():
    """主函数"""
    console = Console()
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description='寻找同画师的压缩包文件')
        parser.add_argument('-c', '--clipboard', action='store_true', help='从剪贴板读取路径')
        parser.add_argument('--ignore-blacklist', action='store_true', help='忽略路径黑名单')
        parser.add_argument('--path', help='要处理的路径')
        parser.add_argument('--min-occurrences', type=int, default=2, help='建立画师文件夹所需的最小文件数（如1则单文件也建文件夹）')
        args = parser.parse_args()
    else:
        console.rule("[bold green]同画师压缩包分类工具 参数设置")
        clipboard = Confirm.ask("是否从剪贴板读取路径?", default=True)
        ignore_blacklist = Confirm.ask("是否忽略路径黑名单?", default=False)
        min_occurrences = Prompt.ask("建立画师文件夹所需的最小文件数（如1则单文件也建文件夹）", default="2")
        path = Prompt.ask("请输入要处理的路径（可留空，回车跳过）", default="")
        class Args:
            pass
        args = Args()
        args.clipboard = clipboard
        args.ignore_blacklist = ignore_blacklist
        args.path = path
        try:
            args.min_occurrences = int(min_occurrences)
        except Exception:
            args.min_occurrences = 2
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
        process_directory(path, ignore_blacklist=args.ignore_blacklist, min_occurrences=args.min_occurrences)
        logger.info(f"✨ 目录处理完成: {path}")

if __name__ == "__main__":
    main()
