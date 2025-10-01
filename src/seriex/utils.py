"""
系列提取工具函数模块
"""

import os
import re
import sys
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Optional, Set, Dict, Any

# 日志：使用 loguru
try:
    from loguru import logger as _loguru_logger  # type: ignore
except Exception:  # pragma: no cover
    _loguru_logger = None  # type: ignore

# TOML 解析器（优先使用内置 tomllib，其次 tomli，若都不可用则置为 None）
toml = None
try:  # Python 3.11+
    import tomllib as toml  # type: ignore
except Exception:
    try:
        import tomli as toml  # type: ignore
    except Exception:
        toml = None

# 中文转换（可选依赖，缺失时退化为原样返回）
try:
    from hanziconv import HanziConv  # type: ignore
except Exception:  # pragma: no cover
    HanziConv = None  # type: ignore

def normalize_chinese(text):
    """标准化中文文本（统一转换为简体）"""
    if HanziConv is None:
        return text
    return HanziConv.toSimplified(text)

def to_traditional(text):
    """简体转繁体"""
    if HanziConv is None:
        return text
    return HanziConv.toTraditional(text)

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

#############################################
# 配置与格式支持
#############################################

_DEFAULT_SUPPORTED_EXTS: Set[str] = {
    # 压缩包家族
    ".zip", ".rar", ".7z", ".cbz", ".cbr",
    # 视频/其它
    ".mp4",
    # 自定义/非通用扩展
    ".nov",
}

_DEFAULT_ARCHIVE_EXTS: Set[str] = {
    ".zip", ".rar", ".7z", ".cbz", ".cbr"
}

_CACHED_CONF: Optional[Dict[str, Any]] = None


def _normalize_exts(exts: Iterable[str]) -> Set[str]:
    """规范化扩展名集合（转小写并补全前导点）。"""
    norm: Set[str] = set()
    for e in exts:
        e = e.strip().lower()
        if not e:
            continue
        if not e.startswith("."):
            e = "." + e
        norm.add(e)
    return norm


def load_seriex_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """加载 seriex 的 TOML 配置。

    优先级：
    1) 明确的 config_path 指向的 toml 文件
    2) 工作目录下的 "seriex.toml"
    3) 工作区或父目录中的 "pyproject.toml" 的 [tool.seriex]
    4) 内置默认值
    """
    global _CACHED_CONF
    if _CACHED_CONF is not None and config_path is None:
        return _CACHED_CONF

    cfg: Dict[str, Any] = {
        "formats": sorted(_DEFAULT_SUPPORTED_EXTS),
        "archive_formats": sorted(_DEFAULT_ARCHIVE_EXTS),
        "prefix": "[#s]",
        "add_prefix": True,
        # 关闭压缩包完整性检查（功能移除，保留配置键向后兼容）
        "check_integrity": False,
        # 已知系列目录（一级子目录名将作为候选系列名），统一存入 known_series_dirs(List[str])
        "known_series_dirs": [],
        # 允许“命中参考系列名”的单文件也单独成组（默认开启）
        "known_series_allow_single": True,
    }

    def _try_load_toml(path: str) -> Optional[Dict[str, Any]]:
        try:
            if toml is None:
                return None
            with open(path, "rb") as f:
                data = toml.load(f)
            return data
        except Exception:
            return None

    data: Optional[Dict[str, Any]] = None
    if config_path:
        data = _try_load_toml(config_path)
    if data is None:
        # 包目录下的默认 seri ex.toml（默认优先）
        pkg_dir = Path(__file__).resolve().parent
        pkg_toml = pkg_dir / "seriex.toml"
        if pkg_toml.exists():
            data = _try_load_toml(str(pkg_toml))
    if data is None:
        # 当前工作目录 seri ex.toml
        cwd_toml = os.path.join(os.getcwd(), "seriex.toml")
        data = _try_load_toml(cwd_toml)
    if data is None:
        # pyproject.toml [tool.seriex]
        # 遍历从 cwd 向上的若干层寻找 pyproject
        cur = Path(os.getcwd())
        for _ in range(5):
            pp = cur / "pyproject.toml"
            if pp.exists():
                project = _try_load_toml(str(pp))
                if project and isinstance(project, dict):
                    tool = project.get("tool") or {}
                    seriex_tool = tool.get("seriex") if isinstance(tool, dict) else None
                    if isinstance(seriex_tool, dict):
                        data = {"seriex": seriex_tool}
                        break
            if cur.parent == cur:
                break
            cur = cur.parent

    if data:
        # 支持两种结构：
        # 1) 直接在根：formats = [], archive_formats = []
        # 2) [seriex] 或 [tool.seriex]
        node = data
        if "seriex" in data and isinstance(data["seriex"], dict):
            node = data["seriex"]

        fmts = node.get("formats") if isinstance(node, dict) else None
        if isinstance(fmts, list):
            cfg["formats"] = sorted(_normalize_exts([str(x) for x in fmts]))

        afmts = node.get("archive_formats") if isinstance(node, dict) else None
        if isinstance(afmts, list):
            cfg["archive_formats"] = sorted(_normalize_exts([str(x) for x in afmts]))

        cintegrity = node.get("check_integrity") if isinstance(node, dict) else None
        if isinstance(cintegrity, bool):
            cfg["check_integrity"] = cintegrity

        cprefix = node.get("prefix") if isinstance(node, dict) else None
        if isinstance(cprefix, str):
            cfg["prefix"] = cprefix

        addp = node.get("add_prefix") if isinstance(node, dict) else None
        if isinstance(addp, bool):
            cfg["add_prefix"] = addp

        # 兼容两种写法：known_series_dir (str) 与 known_series_dirs (list)
        ksd_single = node.get("known_series_dir") if isinstance(node, dict) else None
        ksd_list = node.get("known_series_dirs") if isinstance(node, dict) else None
        merged_dirs: list[str] = []
        if isinstance(ksd_single, str) and ksd_single.strip():
            merged_dirs.append(ksd_single.strip())
        if isinstance(ksd_list, list):
            for p in ksd_list:
                if isinstance(p, str) and p.strip():
                    merged_dirs.append(p.strip())
        if merged_dirs:
            # 去重并保持顺序
            seen = set()
            deduped = []
            for p in merged_dirs:
                if p not in seen:
                    seen.add(p)
                    deduped.append(p)
            cfg["known_series_dirs"] = deduped

        # 是否允许单文件（仅限命中参考系列名）
        allow_single = node.get("known_series_allow_single") if isinstance(node, dict) else None
        if isinstance(allow_single, bool):
            cfg["known_series_allow_single"] = allow_single

    # 兜底保证集合正确
    fmts_set = _normalize_exts(cfg.get("formats", [])) or set(_DEFAULT_SUPPORTED_EXTS)
    afmts_set = _normalize_exts(cfg.get("archive_formats", [])) or set(_DEFAULT_ARCHIVE_EXTS)
    # archive 必须是 formats 的子集，否则取交集
    afmts_set = afmts_set & fmts_set

    cfg["formats"] = sorted(fmts_set)
    cfg["archive_formats"] = sorted(afmts_set)

    if config_path is None:
        _CACHED_CONF = cfg
    return cfg


def get_supported_extensions(config: Optional[Dict[str, Any]] = None) -> Set[str]:
    cfg = config or load_seriex_config()
    return set(cfg.get("formats", _DEFAULT_SUPPORTED_EXTS))


def get_archive_extensions(config: Optional[Dict[str, Any]] = None) -> Set[str]:
    cfg = config or load_seriex_config()
    return set(cfg.get("archive_formats", _DEFAULT_ARCHIVE_EXTS))


def is_supported_file(path: str, config: Optional[Dict[str, Any]] = None) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in get_supported_extensions(config)


def is_archive(path: str, config: Optional[Dict[str, Any]] = None) -> bool:
    """检查文件是否为支持的压缩包格式（基于配置）。"""
    return Path(path).suffix.lower() in get_archive_extensions(config)

# @timeout(60)
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

# 定义系列前缀集合
SERIES_PREFIXES = {
    '[#s]',  # 标准系列标记
    '#',     # 简单系列标记
}

# 定义系列提取黑名单规则
SERIES_BLACKLIST_PATTERNS = [
    r'画集',                # 画集
    r'fanbox',     # artbook/art book（不区分大小写）
    r'pixiv',    # artworks/art works（不区分大小写）
    r'・',          # 插画集（日文）
    r'杂图合集',           # 插画集（中文）
    r'01视频',
    r'02动图',
    r'作品集',             # 作品集
    r'02动图',
    r'损坏压缩包',
]

def is_series_blacklisted(filename):
    """检查文件名是否在系列提取黑名单中"""
    for pattern in SERIES_BLACKLIST_PATTERNS:
        if re.search(pattern, filename, re.IGNORECASE):
            return True
    return False

_LOGGER_CONFIGURED = False

def setup_logger(name: str = 'series_extractor'):
    """提供一个与 logging.Logger 接口相近的记录器，但基于 loguru 实现。

    - 统一格式：时间 - 名称 - 级别 - 消息
    - 返回值为绑定了 name 的 loguru logger，调用方式与原 logger.info/debug 基本一致。
    - 若 loguru 不可用则回退到标准 logging。
    """
    global _LOGGER_CONFIGURED
    if _loguru_logger is None:
        # 回退：使用标准 logging
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        return logger

    # loguru：仅配置一次全局 sink
    if not _LOGGER_CONFIGURED:
        # 简洁、包含名称的格式
        try:
            _loguru_logger.remove()
        except Exception:
            pass
        _loguru_logger.add(
            sink=lambda msg: print(msg, end=''),
            format="{time:YYYY-MM-DD HH:mm:ss} - {extra[name]} - {level} - {message}\n",
            level="INFO",
        )
        _LOGGER_CONFIGURED = True
    # 绑定名称
    return _loguru_logger.bind(name=name)