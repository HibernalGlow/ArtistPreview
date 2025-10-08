"""配置管理模块"""
import streamlit as st
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib

import tomli_w

# 配置文件路径
CONFIG_FILE = Path(__file__).parent / "config.toml"

def load_config():
    """加载配置文件"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'rb') as f:
                return tomllib.load(f)
        except Exception as e:
            st.error(f"加载配置文件失败: {e}")
    return {
        'matching': {'priority_keywords': []},
        'blacklist': {'folders': []}
    }

def save_config(config):
    """保存配置文件"""
    try:
        with open(CONFIG_FILE, 'wb') as f:
            tomli_w.dump(config, f)
        return True
    except Exception as e:
        st.error(f"保存配置文件失败: {e}")
        return False

def load_blacklist():
    """加载黑名单"""
    config = load_config()
    return set(config.get('blacklist', {}).get('folders', []))

def save_blacklist(blacklist):
    """保存黑名单"""
    config = load_config()
    config['blacklist'] = {'folders': list(blacklist)}
    return save_config(config)

def add_to_blacklist(folder_name):
    """添加文件夹到黑名单"""
    blacklist = load_blacklist()
    if folder_name not in blacklist:
        blacklist.add(folder_name)
        if save_blacklist(blacklist):
            st.success(f"已将 '{folder_name}' 添加到黑名单")
            return True
    else:
        st.warning(f"'{folder_name}' 已在黑名单中")
    return False

def load_folder_blacklist():
    """加载文件夹黑名单"""
    config = load_config()
    return config.get('folder_moving', {}).get('blacklist', [])

def save_folder_blacklist(folder_blacklist):
    """保存文件夹黑名单"""
    config = load_config()
    if 'folder_moving' not in config:
        config['folder_moving'] = {}
    config['folder_moving']['blacklist'] = folder_blacklist
    return save_config(config)

def is_folder_blacklisted(folder_name, folder_blacklist):
    """检查文件夹是否在黑名单中（支持正则匹配）"""
    import re
    for pattern in folder_blacklist:
        try:
            if re.search(pattern, folder_name, re.IGNORECASE):
                return True
        except re.error:
            # 如果正则表达式无效，当作普通字符串匹配
            if pattern.lower() in folder_name.lower():
                return True
    return False