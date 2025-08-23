from __future__ import annotations
from pathlib import Path
from typing import List, Iterable, Optional
from .models import ArtistRecord
from .store import ArtistStore
from datetime import datetime
import json
import os

# --- 纯函数：从文件夹名提取可用于匹配的名字（不写入数据库） ---
def extract_names_from_folder_name(folder_name: str, exclude_keywords: Optional[List[str]] = None) -> List[str]:
    """根据 lista 的解析规则，从单个文件夹名中提取用于匹配的名字列表。

    规则与 scan_folder 内部一致：
    - 仅当文件夹名以 '[' 开头时尝试解析
    - 形如 "[社团(画师1、画师2)]" 会抽取 画师* 与 社团名；以 '、' 分隔多个
    - 无括号 "()" 时，取中括号内的整体作为一个名字
    - 过滤包含排除关键字的名字
    """
    def _load_config() -> dict:
        try:
            base_dir = Path(__file__).resolve().parent.parent
            cfg_path = base_dir / 'config.json'
            if cfg_path.exists():
                return json.loads(cfg_path.read_text(encoding='utf-8'))
        except Exception:
            pass
        return {}

    cfg = _load_config()
    excludes = exclude_keywords if exclude_keywords is not None else list(cfg.get('exclude_keywords', [])) or [
        "汉化","翻译","Chinese","中文","简体","繁体",".zip",".rar",".7z"
    ]
    group_delims: List[str] = list(cfg.get('group_delimiters', ['／']))

    # 将字符串拆成多个组（顶层用分隔符切分，避免中括号内部被切分）
    def split_top_level(s: str, delims: List[str]) -> List[str]:
        parts: List[str] = []
        buf: List[str] = []
        i = 0
        depth = 0
        while i < len(s):
            ch = s[i]
            if ch == '[':
                depth += 1
                buf.append(ch)
                i += 1
                continue
            if ch == ']':
                depth = max(0, depth - 1)
                buf.append(ch)
                i += 1
                continue
            if depth == 0:
                matched = False
                for d in delims:
                    if d and s.startswith(d, i):
                        # 命中分隔符 -> 切分
                        parts.append(''.join(buf).strip())
                        buf.clear()
                        i += len(d)
                        matched = True
                        break
                if matched:
                    continue
            # 默认累加
            buf.append(ch)
            i += 1
        if buf:
            parts.append(''.join(buf).strip())
        # 去掉空项
        return [p for p in parts if p]

    # 提取每个 [..] 内的内容
    def extract_bracket_contents(s: str) -> List[str]:
        res: List[str] = []
        i = 0
        while i < len(s):
            if s[i] == '[':
                j = i + 1
                # 找到匹配的 ']'
                while j < len(s) and s[j] != ']':
                    j += 1
                content = s[i+1:j] if j < len(s) else s[i+1:]
                res.append(content.strip())
                i = j + 1 if j < len(s) else len(s)
            else:
                i += 1
        return res

    folder = folder_name.strip()
    if not folder:
        return []

    groups = split_top_level(folder, group_delims)
    raw_names: List[str] = []
    for grp in groups:
        # 支持直接为一个 [..] 组，或包含多个 [..] 组
        contents = extract_bracket_contents(grp) if '[' in grp else [grp]
        for clean_name in contents:
            if '(' in clean_name:
                circle_part = clean_name.split('(')[0].strip()
                artist_part = clean_name.split('(')[1].rstrip(')').strip()
                artist_names = [n.strip() for n in artist_part.split('、') if n.strip()]
                circle_names = [n.strip() for n in circle_part.split('、') if n.strip()]
                raw_names.extend(artist_names + circle_names)
            else:
                raw_names.append(clean_name.strip())

    # 过滤排除关键字
    valid = [n for n in raw_names if n and not any(k in n for k in excludes)]
    # 去重并保持顺序
    seen = set()
    ordered = []
    for n in valid:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return ordered

class ArtistService:
    def __init__(self, store: ArtistStore, config: dict):
        self.store = store
        self.config = config

    def scan_folder(self, base: Path, category: str = 'auto') -> int:
        if not base.exists():
            return 0
        records: List[ArtistRecord] = []
        for f in base.iterdir():
            if f.is_dir() and f.name.startswith('['):
                valid = extract_names_from_folder_name(f.name, exclude_keywords=self.config.get('exclude_keywords', []))
                if not valid:
                    continue
                records.append(ArtistRecord(folder=f.name, names=valid, category=category, source='auto'))
        return self.store.bulk_upsert(records)

    def add_manual(self, folder: str, names: List[str], category: str):
        self.store.upsert(ArtistRecord(folder=folder, names=names, category=category, source='user'))

    def set_category(self, name_or_folder: str, category: str) -> int:
        return self.store.set_category(name_or_folder, category)

    def remove(self, name_or_folder: str) -> int:
        return self.store.remove(name_or_folder)

