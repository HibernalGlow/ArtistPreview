import os
import sys
import shutil
import re
import json
import argparse
import pyperclip
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Set
import send2trash
from opencc import OpenCC
import webbrowser
import tempfile
import time

# 添加父目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(script_dir))
sys.path.append(parent_dir)

from nodes.record.logger_config import setup_logger
from nodes.tui.textual_logger import TextualLoggerManager
from nodes.tui.preset.textual_preset import create_config_app
from nodes.error.error_handler import handle_file_operation

# 定义日志布局配置
TEXTUAL_LAYOUT = {
    "current_stats": {
        "ratio": 2,
        "title": "📊 总体统计",
        "style": "lightyellow"
    },
    "current_progress": {
        "ratio": 2,
        "title": "🔄 移动进度",
        "style": "lightcyan"
    },
    "artist_info": {
        "ratio": 3,
        "title": "🎨 画师信息",
        "style": "lightmagenta"
    },
    "conflict_log": {
        "ratio": 2,
        "title": "⚠️ 冲突记录",
        "style": "pink"
    },
    "process_log": {
        "ratio": 3,
        "title": "📝 处理日志",
        "style": "lightblue"
    }
}

# 设置日志配置
config = {
    'script_name': 'move_artist_folders',
    'console_enabled': False  # 禁用控制台输出，使用TextualLogger代替
}

# 初始化日志系统
logger, config_info = setup_logger(config)

def init_TextualLogger():
    """初始化TextualLogger"""
    TextualLoggerManager.set_layout(TEXTUAL_LAYOUT, config_info['log_file'])
    logger.info("[#update]✅ 日志系统初始化完成")
    
# 初始化 OpenCC
cc_s2t = OpenCC('s2t')  # 简体到繁体
cc_t2s = OpenCC('t2s')  # 繁体到简体

# 画师名称匹配模式
ARTIST_PATTERN = re.compile(r'\[(.*?)(?:\s*\((.*?)\))?\]')

def normalize_artist_name(name: str) -> str:
    """
    标准化画师名称，处理简繁体差异和格式差异
    """
    # 去除空格和转换为小写
    name = name.lower().strip()
    
    # 转为简体
    simplified = cc_t2s.convert(name)
    
    # 移除常见不影响画师识别的字符
    simplified = re.sub(r'[_\-.,;:!?\s]', '', simplified)
    
    return simplified

def extract_artist_info(folder_name: str) -> Tuple[str, str]:
    """
    从文件夹名称中提取画师信息
    返回格式: (社团名, 画师名)
    """
    match = ARTIST_PATTERN.search(folder_name)
    if match:
        full_match = match.group(0)
        if '(' in full_match:
            # 格式为 [社团 (画师)]
            group = match.group(1).strip()
            artist = match.group(2).strip() if match.group(2) else ""
            return group, artist
        else:
            # 格式为 [画师]
            return "", match.group(1).strip()
    
    # 未能匹配到画师格式，返回空
    return "", ""

def is_artist_folder(folder_name: str) -> bool:
    """
    判断文件夹是否是画师文件夹
    """
    # 检查是否匹配画师模式
    match = ARTIST_PATTERN.search(folder_name)
    if not match:
        return False
    
    # 排除特定类型的文件夹
    blacklist = [
        '00', 'temp', 'trash', 'backup', 'wait', 
        '归档', '未分类', '暂存', '待处理', '其他'
    ]
    
    for keyword in blacklist:
        if keyword.lower() in folder_name.lower():
            return False
    
    return True

def are_artists_same(name1: str, name2: str) -> bool:
    """
    比较两个画师名称是否指向同一画师
    """
    # 提取画师信息
    group1, artist1 = extract_artist_info(name1)
    group2, artist2 = extract_artist_info(name2)
    
    # 如果画师名为空，则不匹配
    if not artist1 or not artist2:
        return False
    
    # 标准化名称进行比较
    norm_artist1 = normalize_artist_name(artist1)
    norm_artist2 = normalize_artist_name(artist2)
    
    # 如果画师名相同，则认为是同一画师
    if norm_artist1 and norm_artist2 and norm_artist1 == norm_artist2:
        return True
    
    # 社团和画师都相同的情况
    if group1 and group2:
        norm_group1 = normalize_artist_name(group1)
        norm_group2 = normalize_artist_name(group2)
        if norm_group1 == norm_group2 and norm_artist1 == norm_artist2:
            return True
    
    return False

def create_wait_folder(target_dir: str) -> str:
    """
    在目标目录创建或确保存在[02wait]文件夹
    """
    wait_folder = os.path.join(target_dir, "[02wait]")
    try:
        os.makedirs(wait_folder, exist_ok=True)
        logger.info(f"[#process_log]确保待处理文件夹存在: {wait_folder}")
    except Exception as e:
        logger.info(f"[#process_log]创建待处理文件夹失败: {e}")
    
    return wait_folder

def get_conflict_folders(source_dir: str, target_dir: str) -> Dict[str, List[str]]:
    """
    查找源目录和目标目录中同名或指向同一画师的文件夹
    返回: {源文件夹名: [对应目标文件夹列表]}
    """
    conflicts = {}
    
    # 获取目标目录的所有一级文件夹
    target_folders = [f for f in os.listdir(target_dir) 
                     if os.path.isdir(os.path.join(target_dir, f))]
    
    # 过滤掉不是画师文件夹的特殊文件夹
    target_artist_folders = [f for f in target_folders if is_artist_folder(f)]
    
    # 获取源目录的所有一级文件夹
    for src_folder in os.listdir(source_dir):
        src_path = os.path.join(source_dir, src_folder)
        
        # 只处理文件夹且符合画师文件夹命名规范
        if not os.path.isdir(src_path) or not is_artist_folder(src_folder):
            continue
        
        # 查找冲突
        conflicting_targets = []
        
        # 1. 首先检查完全相同的文件夹名
        if src_folder in target_folders:
            conflicting_targets.append(src_folder)
            continue  # 如果名称完全相同，不需要再进行画师名比较
        
        # 2. 检查指向同一画师的不同格式文件夹名
        for target_folder in target_artist_folders:
            if are_artists_same(src_folder, target_folder):
                conflicting_targets.append(target_folder)
        
        # 如果有冲突，记录
        if conflicting_targets:
            conflicts[src_folder] = conflicting_targets
    
    return conflicts

@handle_file_operation(skip_errors=True)
def move_folder(src_path: str, dst_path: str) -> bool:
    """
    安全移动文件夹
    """
    try:
        # 如果目标路径已存在，先尝试安全删除
        if os.path.exists(dst_path):
            logger.info(f"[#conflict_log]目标路径已存在，尝试移动到回收站: {dst_path}")
            send2trash.send2trash(dst_path)
        
        # 移动文件夹
        shutil.move(src_path, dst_path)
        return True
    except Exception as e:
        logger.info(f"[#process_log]移动文件夹失败: {src_path} -> {dst_path}")
        logger.info(f"[#process_log]错误信息: {str(e)}")
        return False

def generate_html_confirmation(source_dir: str, target_dir: str, source_folders: List[str], conflict_map: Dict[str, List[str]]) -> str:
    """
    生成HTML确认页面
    """
    # 创建临时HTML文件
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8')
    
    # HTML内容
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>画师文件夹移动确认</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            h1, h2, h3 {{
                color: #333;
            }}
            .section {{
                background-color: white;
                padding: 15px;
                margin-bottom: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .folders-list {{
                max-height: 300px;
                overflow-y: auto;
                border: 1px solid #ddd;
                padding: 10px;
                margin: 10px 0;
                background-color: #fafafa;
            }}
            .folder-item {{
                padding: 5px;
                border-bottom: 1px solid #eee;
            }}
            .folder-item:last-child {{
                border-bottom: none;
            }}
            .conflict {{
                color: #d9534f;
                font-weight: bold;
            }}
            .conflict-details {{
                margin-left: 20px;
                color: #777;
                font-style: italic;
            }}
            .button-container {{
                text-align: center;
                margin-top: 30px;
            }}
            .confirm-button {{
                background-color: #5cb85c;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 16px;
                cursor: pointer;
                border-radius: 5px;
                margin-right: 10px;
            }}
            .cancel-button {{
                background-color: #d9534f;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 16px;
                cursor: pointer;
                border-radius: 5px;
            }}
            .summary {{
                font-weight: bold;
                margin-bottom: 10px;
            }}
        </style>
    </head>
    <body>
        <h1>画师文件夹移动确认</h1>
        
        <div class="section">
            <h2>移动概要</h2>
            <p><strong>源目录:</strong> {source_dir}</p>
            <p><strong>目标目录:</strong> {target_dir}</p>
            <div class="summary">
                <p>总计画师文件夹: {len(source_folders)} 个</p>
                <p>存在冲突文件夹: {len(conflict_map)} 个</p>
            </div>
        </div>
        
        <div class="section">
            <h2>待移动文件夹列表</h2>
            <div class="folders-list">
    """
    
    # 添加文件夹列表
    for folder in source_folders:
        group, artist = extract_artist_info(folder)
        artist_info = f"社团: {group}, 画师: {artist}" if group else f"画师: {artist}"
        
        if folder in conflict_map:
            html_content += f"""
                <div class="folder-item conflict">
                    {folder} ({artist_info}) - 存在冲突!
                    <div class="conflict-details">
                        冲突文件夹: {', '.join(conflict_map[folder])}
                    </div>
                </div>
            """
        else:
            html_content += f"""
                <div class="folder-item">
                    {folder} ({artist_info})
                </div>
            """
    
    # 添加确认按钮和说明
    html_content += """
            </div>
        </div>
        
        <div class="section">
            <h2>操作说明</h2>
            <p>点击"确认移动"按钮将执行以下操作:</p>
            <ul>
                <li>对于存在冲突的文件夹，会先将目标目录中的同名文件夹移动到[02wait]文件夹</li>
                <li>然后将源目录中的所有画师文件夹移动到目标目录</li>
            </ul>
            <p>如果您不想继续，请点击"取消"按钮。</p>
        </div>
        
        <div class="button-container">
            <button class="confirm-button" onclick="confirmMove()">确认移动</button>
            <button class="cancel-button" onclick="cancelMove()">取消</button>
        </div>
        
        <script>
            function confirmMove() {
                // 创建一个标记文件表示用户确认
                fetch('confirm.html', {method: 'POST'})
                    .then(() => {
                        document.body.innerHTML = '<h1>已确认，正在执行移动操作...</h1><p>请关闭此页面并返回程序。</p>';
                    })
                    .catch(err => {
                        console.error(err);
                        // 如果fetch失败，也创建一个确认文件
                        const link = document.createElement('a');
                        link.href = 'data:text/plain;charset=utf-8,confirmed';
                        link.download = 'confirm.txt';
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                        document.body.innerHTML = '<h1>已确认，正在执行移动操作...</h1><p>请关闭此页面并返回程序。</p>';
                    });
            }
            
            function cancelMove() {
                // 创建一个标记文件表示用户取消
                fetch('cancel.html', {method: 'POST'})
                    .then(() => {
                        document.body.innerHTML = '<h1>已取消操作</h1><p>请关闭此页面并返回程序。</p>';
                    })
                    .catch(err => {
                        console.error(err);
                        // 如果fetch失败，也创建一个取消文件
                        const link = document.createElement('a');
                        link.href = 'data:text/plain;charset=utf-8,canceled';
                        link.download = 'cancel.txt';
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                        document.body.innerHTML = '<h1>已取消操作</h1><p>请关闭此页面并返回程序。</p>';
                    });
            }
        </script>
    </body>
    </html>
    """
    
    # 写入HTML文件
    temp_file.write(html_content)
    temp_file.close()
    
    return temp_file.name

def wait_for_confirmation(html_file_path: str) -> bool:
    """
    打开HTML确认页面并等待用户确认
    返回用户是否确认
    """
    # 打开HTML文件
    webbrowser.open('file://' + html_file_path)
    
    # 创建确认和取消的文件路径
    confirm_file = os.path.join(os.path.dirname(html_file_path), 'confirm.txt')
    cancel_file = os.path.join(os.path.dirname(html_file_path), 'cancel.txt')
    
    # 删除可能存在的旧文件
    for file in [confirm_file, cancel_file]:
        if os.path.exists(file):
            os.remove(file)
    
    logger.info(f"[#process_log]已打开确认页面，等待用户确认...")
    
    # 等待用户操作
    while True:
        if os.path.exists(confirm_file):
            logger.info(f"[#process_log]用户已确认操作")
            os.remove(confirm_file)
            os.remove(html_file_path)
            return True
        
        if os.path.exists(cancel_file):
            logger.info(f"[#process_log]用户已取消操作")
            os.remove(cancel_file)
            os.remove(html_file_path)
            return False
        
        time.sleep(0.5)  # 暂停一下，减少CPU使用

def process_directory_pair(source_dir: str, target_dir: str, dry_run: bool = False) -> Dict:
    """
    处理一对目录，移动源目录中的画师文件夹到目标目录
    遇到冲突时将目标目录中的文件夹移至[02wait]
    """
    results = {
        "total_folders": 0,
        "moved_folders": 0,
        "conflicts": 0,
        "moved_conflicts": 0,
        "errors": 0
    }
    
    logger.info(f"[#current_stats]开始处理目录对: {source_dir} -> {target_dir}")
    
    # 确保源目录和目标目录都存在
    if not os.path.exists(source_dir):
        logger.info(f"[#process_log]源目录不存在: {source_dir}")
        return results
    
    if not os.path.exists(target_dir):
        logger.info(f"[#process_log]目标目录不存在: {target_dir}")
        return results
    
    # 创建待处理文件夹
    wait_folder = create_wait_folder(target_dir)
    
    # 查找潜在冲突
    conflict_map = get_conflict_folders(source_dir, target_dir)
    
    # 获取需要处理的源文件夹
    source_folders = [f for f in os.listdir(source_dir) 
                     if os.path.isdir(os.path.join(source_dir, f)) and is_artist_folder(f)]
    
    results["total_folders"] = len(source_folders)
    results["conflicts"] = len(conflict_map)
    logger.info(f"[#current_stats]待处理画师文件夹: {len(source_folders)}")
    logger.info(f"[#current_stats]冲突文件夹: {len(conflict_map)}")
    
    # 显示冲突信息
    if conflict_map:
        logger.info(f"[#conflict_log]检测到 {len(conflict_map)} 个画师冲突:")
        for src_folder, target_folders in conflict_map.items():
            group, artist = extract_artist_info(src_folder)
            artist_info = f"社团: {group}, 画师: {artist}" if group else f"画师: {artist}"
            logger.info(f"[#artist_info]{src_folder} ({artist_info}) 与以下文件夹冲突:")
            for target_folder in target_folders:
                logger.info(f"[#conflict_log] - {target_folder}")
    
    # 如果是预演模式，提前返回
    if dry_run:
        logger.info(f"[#process_log]预演模式：不执行实际移动操作")
        return results
    
    # 生成确认页面并等待用户确认
    html_file = generate_html_confirmation(source_dir, target_dir, source_folders, conflict_map)
    logger.info(f"[#process_log]已生成确认页面: {html_file}")
    
    if not wait_for_confirmation(html_file):
        logger.info(f"[#process_log]用户取消了操作，退出")
        return results
    
    # 处理所有源文件夹
    for i, folder in enumerate(source_folders):
        src_path = os.path.join(source_dir, folder)
        
        # 更新进度
        progress = ((i + 1) / len(source_folders)) * 100
        logger.info(f"[@current_progress]处理中 ({i + 1}/{len(source_folders)}) {progress:.1f}%")
        
        # 如果是冲突文件夹，先处理冲突
        if folder in conflict_map:
            for conflict_folder in conflict_map[folder]:
                conflict_path = os.path.join(target_dir, conflict_folder)
                conflict_wait_path = os.path.join(wait_folder, conflict_folder)
                
                # 如果wait目录下已存在同名文件夹，先添加时间戳
                if os.path.exists(conflict_wait_path):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    conflict_wait_path = os.path.join(wait_folder, f"{timestamp}_{conflict_folder}")
                    logger.info(f"[#conflict_log]待处理区已存在同名文件夹，添加时间戳: {timestamp}_{conflict_folder}")
                
                logger.info(f"[#conflict_log]移动冲突文件夹到待处理区: {conflict_folder}")
                
                if move_folder(conflict_path, conflict_wait_path):
                    results["moved_conflicts"] += 1
                    logger.info(f"[#process_log]已移动冲突文件夹: {conflict_folder} -> [02wait]/{os.path.basename(conflict_wait_path)}")
                else:
                    results["errors"] += 1
                    logger.info(f"[#process_log]移动冲突文件夹失败: {conflict_folder}")
        
        # 移动源文件夹到目标目录
        dst_path = os.path.join(target_dir, folder)
        logger.info(f"[#process_log]移动文件夹: {folder}")
        
        if move_folder(src_path, dst_path):
            results["moved_folders"] += 1
            
            # 输出画师信息
            group, artist = extract_artist_info(folder)
            artist_info = f"社团: {group}, 画师: {artist}" if group else f"画师: {artist}"
            logger.info(f"[#artist_info]已移动画师: {folder} ({artist_info})")
        else:
            results["errors"] += 1
            logger.info(f"[#process_log]移动文件夹失败: {folder}")
    
    # 显示汇总信息
    logger.info(f"[@current_progress]✅ 完成 ({len(source_folders)}/{len(source_folders)}) 100%")
    logger.info(f"[#current_stats]总计处理: {results['total_folders']} 个画师文件夹")
    logger.info(f"[#current_stats]成功移动: {results['moved_folders']} 个文件夹")
    logger.info(f"[#current_stats]处理冲突: {results['moved_conflicts']} 个文件夹")
    logger.info(f"[#current_stats]错误数量: {results['errors']} 个")
    
    return results

def get_paths_from_clipboard() -> List[str]:
    """从剪贴板读取多行路径"""
    try:
        clipboard_content = pyperclip.paste()
        if not clipboard_content:
            return []
        
        paths = [
            path.strip().strip('"').strip("'")
            for path in clipboard_content.splitlines() 
            if path.strip()
        ]
        
        valid_paths = [
            path for path in paths 
            if os.path.exists(path)
        ]
        
        if valid_paths:
            logger.info(f"[#process_log]从剪贴板读取到 {len(valid_paths)} 个有效路径")
        else:
            logger.info(f"[#process_log]剪贴板中没有有效路径")
            
        return valid_paths
        
    except Exception as e:
        logger.info(f"[#process_log]读取剪贴板时出错: {e}")
        return []

def run_command_line():
    """命令行模式执行"""
    parser = argparse.ArgumentParser(description='移动画师文件夹工具')
    parser.add_argument('-c', '--clipboard', action='store_true', help='从剪贴板读取路径')
    parser.add_argument('--source', help='源目录路径')
    parser.add_argument('--target', help='目标目录路径')
    parser.add_argument('--dry-run', action='store_true', help='预演模式，不实际移动文件')
    args = parser.parse_args()
    
    # 获取目录对
    directory_pairs = []
    
    if args.clipboard:
        paths = get_paths_from_clipboard()
        if len(paths) >= 2 and len(paths) % 2 == 0:
            for i in range(0, len(paths), 2):
                directory_pairs.append((paths[i], paths[i+1]))
        else:
            logger.info(f"[#process_log]剪贴板路径数量不正确或不均匀")
    
    if args.source and args.target:
        directory_pairs.append((args.source, args.target))
    
    # 如果没有有效的目录对，使用默认值
    if not directory_pairs:
        directory_pairs = [
            ("E:\\1Hub\\EH\\999EHV", "E:\\1Hub\\EH\\1EHV"),
        ]
    
    # 处理所有目录对
    for source_dir, target_dir in directory_pairs:
        logger.info(f"[#current_stats]处理目录对: {source_dir} -> {target_dir}")
        process_directory_pair(source_dir, target_dir, dry_run=args.dry_run)

def main_tui():
    """TUI界面模式入口"""
    # 定义复选框选项
    checkbox_options = [
        ("从剪贴板读取路径", "clipboard", "-c"),
        ("预演模式", "dry_run", "--dry-run"),
    ]

    # 定义输入框选项
    input_options = [
        ("源目录", "source", "--source", "E:\\1Hub\\EH\\999EHV", "输入源目录路径"),
        ("目标目录", "target", "--target", "E:\\1Hub\\EH\\1EHV", "输入目标目录路径"),
    ]

    # 预设配置
    preset_configs = {
        "标准模式": {
            "description": "将E:\\1Hub\\EH\\999EHV下的画师文件夹移动到E:\\1Hub\\EH\\1EHV",
            "checkbox_options": [],
            "input_values": {"source": "E:\\1Hub\\EH\\999EHV", "target": "E:\\1Hub\\EH\\1EHV"}
        },
        "预演模式": {
            "description": "预览将要执行的操作，不实际移动文件",
            "checkbox_options": ["dry_run"],
            "input_values": {"source": "E:\\1Hub\\EH\\999EHV", "target": "E:\\1Hub\\EH\\1EHV"}
        },
        "剪贴板模式": {
            "description": "从剪贴板读取目录对(每两行一对)",
            "checkbox_options": ["clipboard"],
            "input_values": {"source": "", "target": ""}
        }
    }

    # 定义回调函数
    def on_run(params: dict):
        """TUI配置界面的回调函数"""
        # 从参数中提取值
        use_clipboard = params['options'].get('clipboard', False)
        dry_run = params['options'].get('dry_run', False)
        source_dir = params['inputs'].get('source', '')
        target_dir = params['inputs'].get('target', '')
        
        directory_pairs = []
        
        # 处理剪贴板输入
        if use_clipboard:
            paths = get_paths_from_clipboard()
            if len(paths) >= 2 and len(paths) % 2 == 0:
                for i in range(0, len(paths), 2):
                    directory_pairs.append((paths[i], paths[i+1]))
            else:
                logger.info(f"[#process_log]剪贴板路径数量不正确，需要偶数个路径")
        
        # 处理手动输入
        if source_dir and target_dir:
            directory_pairs.append((source_dir, target_dir))
        
        # 如果没有有效的目录对，使用默认值
        if not directory_pairs:
            directory_pairs = [
                ("E:\\1Hub\\EH\\999EHV", "E:\\1Hub\\EH\\1EHV"),
            ]
        init_TextualLogger()
        # 处理所有目录对
        for source, target in directory_pairs:
            logger.info(f"[#current_stats]处理目录对: {source} -> {target}")
            process_directory_pair(source, target, dry_run=dry_run)

    # 创建并运行配置界面
    app = create_config_app(
        program=__file__,
        title="画师文件夹移动工具",
        checkbox_options=checkbox_options,
        input_options=input_options,
        preset_configs=preset_configs,
        on_run=on_run
    )
    app.run()

def main():
    """主函数入口"""
    # 如果没有命令行参数，启动TUI界面
    if len(sys.argv) == 1:
        main_tui()
    else:
        # 否则使用命令行模式
        run_command_line()

if __name__ == "__main__":
    main()
