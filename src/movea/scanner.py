"""目录扫描和匹配模块"""
import streamlit as st
import os
import re
from pathlib import Path
from .config import load_blacklist, load_config
from .file_ops import is_archive

def scan_directory(root_path):
    """扫描根路径下的每个一级文件夹"""
    if not os.path.exists(root_path):
        st.error(f"路径不存在: {root_path}")
        return {}

    # 加载黑名单
    blacklist = load_blacklist()

    results = {}
    try:
        # 获取一级文件夹
        for item in os.listdir(root_path):
            level1_path = os.path.join(root_path, item)
            if os.path.isdir(level1_path):
                # 跳过黑名单中的文件夹
                if item in blacklist:
                    continue

                # 获取二级文件夹、压缩包和可移动文件夹
                subfolders = []
                archives = []
                movable_folders = []
                for subitem in os.listdir(level1_path):
                    subitem_path = os.path.join(level1_path, subitem)
                    if os.path.isdir(subitem_path):
                        subfolders.append(subitem)
                    elif os.path.isfile(subitem_path) and is_archive(subitem_path):
                        archives.append(subitem)

                # 可移动的文件夹：一级文件夹下的文件夹，但排除已存在的二级文件夹
                # 暂时先添加一个简单的逻辑：如果文件夹名不包含数字前缀，就认为是可移动的文件夹
                movable_folders = []
                for folder in subfolders[:]:  # 复制一份
                    if not re.match(r'^\d+[\.\)\]\s]*', folder):  # 如果不是以数字开头的
                        movable_folders.append(folder)
                        subfolders.remove(folder)  # 从二级文件夹中移除

                if (archives or movable_folders) and subfolders:  # 有可移动对象且有目标文件夹
                    results[item] = {
                        'path': level1_path,
                        'subfolders': sorted(subfolders),  # 排序二级文件夹
                        'archives': archives,
                        'movable_folders': movable_folders
                    }
    except Exception as e:
        st.error(f"扫描目录时出错: {e}")

    return results

def match_archive_to_folder(archive_name, subfolders, regex_patterns, allow_move_to_unnumbered=False):
    """使用正则匹配压缩包到二级文件夹，优先选择包含关键词的文件夹"""
    config = load_config()
    priority_keywords = config.get('matching', {}).get('priority_keywords', [])

    # 先找到所有正则匹配的文件夹
    matched_folders = []
    for folder in subfolders:
        for pattern in regex_patterns:
            try:
                if re.search(pattern, archive_name, re.IGNORECASE):
                    matched_folders.append(folder)
                    break  # 找到匹配就停止
            except re.error:
                continue  # 忽略无效的正则表达式

    # 如果允许移动到无编号文件夹，添加没有编号的文件夹（但排除自身）
    if allow_move_to_unnumbered:
        # 定义编号模式
        number_patterns = [
            r'^\d+\.\s*',  # "1. ", "01. " 等
            r'^\(\d+\)\s*',  # "(1) ", "(01) " 等
            r'^\[\d+\]\s*',  # "[1] ", "[01] " 等
        ]

        unnumbered_folders = []
        for folder in subfolders:
            has_number = False
            for pattern in number_patterns:
                if re.match(pattern, folder):
                    has_number = True
                    break
            if not has_number:
                unnumbered_folders.append(folder)

        # 将无编号文件夹添加到匹配列表，但不包括已经在matched_folders中的
        for folder in unnumbered_folders:
            if folder not in matched_folders:
                matched_folders.append(folder)

    if not matched_folders:
        return []

    # 在匹配的文件夹中，优先选择包含关键词的文件夹
    priority_folders = []
    regular_folders = []

    for folder in matched_folders:
        is_priority = any(keyword.lower() in folder.lower() for keyword in priority_keywords)
        if is_priority:
            priority_folders.append(folder)
        else:
            regular_folders.append(folder)

    # 返回优先文件夹 + 普通文件夹
    return priority_folders + regular_folders