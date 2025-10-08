"""
serima 工具函数模块
"""

import os
import re
import sys
import subprocess
import logging
from pathlib import Path
from hanziconv import HanziConv

def normalize_chinese(text):
    """标准化中文文本（统一转换为简体）"""
    return HanziConv.toSimplified(text)

# 设置文件系统编码
# if sys.platform == 'win32':
#     try:
#         import win32api
#         def win32_path_exists(path):
#             try:
#                 win32api.GetFileAttributes(path)
#                 return True
#             except:
#                 print("未安装win32api模块，某些路径可能无法正确处理")
#                 return os.path.exists(path)
#     except ImportError:
#         print("未安装win32api模块，某些路径可能无法正确处理")
#         win32_path_exists = os.path.exists

# 定义支持的图片扩展名
IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.jxl', '.avif', '.heic', '.heif', '.jfif',
    '.tiff', '.tif', '.psd', '.xcf'
}

# 定义路径黑名单关键词
PATH_BLACKLIST = {
    '画集',
    '01视频',
    '02动图',
    '损坏压缩包',
}

def is_archive(path):
    """检查文件是否为支持的压缩包格式"""
    return Path(path).suffix.lower() in {'.zip', '.rar', '.7z', '.cbz', '.cbr'}

def is_path_blacklisted(path):
    """检查路径是否在黑名单中"""
    # 转换为小写进行比较
    path_lower = path.lower()
    return any(keyword.lower() in path_lower for keyword in PATH_BLACKLIST)

class TimeoutError(Exception):
    """超时异常"""
    pass

def timeout(seconds):
    """超时装饰器"""
    def decorator(func):
        import functools
        import threading
        import signal
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            def handler(signum, frame):
                raise TimeoutError(f"函数执行超时 ({seconds}秒)")

            # 设置信号处理器
            if sys.platform != 'win32':  # Unix系统使用信号
                original_handler = signal.signal(signal.SIGALRM, handler)
                signal.alarm(seconds)
            else:  # Windows系统使用线程
                timer = threading.Timer(seconds, lambda: threading._shutdown())
                timer.start()

            try:
                result = func(*args, **kwargs)
            finally:
                if sys.platform != 'win32':  # Unix系统
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, original_handler)
                else:  # Windows系统
                    timer.cancel()

            return result
        return wrapper
    return decorator

@timeout(60)
def is_archive_corrupted(archive_path):
    """检查压缩包是否损坏"""
    try:
        # 使用7z测试压缩包完整性
        cmd = ['7z', 't', archive_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=55)
        return result.returncode != 0
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"检查压缩包完整性超时: {archive_path}")
    except Exception:
        return True

@timeout(60)
def run_7z_command(command, archive_path, operation="", additional_args=None):
    """运行7z命令并返回输出"""
    try:
        # 基础命令
        cmd = ['7z', command]
        if additional_args:
            cmd.extend(additional_args)
        cmd.append(archive_path)
        
        # 运行命令并捕获输出
        # 使用cp932编码(日文Windows默认编码)来处理输出
        result = subprocess.run(cmd, capture_output=True, text=False, timeout=55)
        try:
            # 首先尝试使用cp932解码
            output = result.stdout.decode('cp932')
        except UnicodeDecodeError:
            try:
                # 如果cp932失败，尝试utf-8
                output = result.stdout.decode('utf-8')
            except UnicodeDecodeError:
                # 如果都失败，使用errors='replace'来替换无法解码的字符
                output = result.stdout.decode('utf-8', errors='replace')
        
        return output if output else ""
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"7z命令执行超时: {archive_path}")
    except Exception as e:
        print(f"执行7z命令时出错 {archive_path}: {str(e)}")
        return ""

def setup_logger(name='manga_serialize'):
    """设置日志"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # 添加处理器到日志器
    logger.addHandler(console_handler)
    
    return logger