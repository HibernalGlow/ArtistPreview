#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
画师信息维护工具

这个工具专门用于维护和管理画师数据库，包括：
- 自动扫描并更新画师文件夹列表
- 添加、删除用户自定义画师
- 搜索和列出画师信息
- 显示画师统计信息

作者: Lista
创建时间: 2025年7月14日
"""

import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from loguru import logger
import sys
from datetime import datetime
from tinydb import TinyDB, Query
import pyperclip

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
        # 去除表情符号以兼容 Windows GBK 控制台
        logger.add(
            sys.stdout,
            level="INFO",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <blue>{elapsed}</blue> | <level>{level: <8}</level> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>"
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
    format="{time:YYYY-MM-DD HH:mm:ss} | {elapsed} | {level: <8} | {name}:{function}:{line} - {message}",
    enqueue=True,     )
    
    # 创建配置信息字典
    config_info = {
        'log_file': log_file,
    }
    
    logger.info(f"日志系统已初始化，应用名称: {app_name}")
    return logger, config_info

logger, config_info = setup_logger(app_name="lista", console_output=True)


def _safe_print(text: str):
    """兼容 Windows 控制台的安全打印，必要时回退到替换无法编码字符"""
    try:
        print(text)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or 'utf-8'
        print(text.encode(enc, errors='replace').decode(enc, errors='replace'))


class ArtistInfoManager:
    """画师信息管理器 (TinyDB 版本) - 负责维护和管理画师数据库

    数据结构 (TinyDB 单表 artists):
        {
          'names': ["主名", "别名1", ...],
          'folder': "[xxx]",             # 原始文件夹名
          'category': "auto|white|black|custom...",
          'source': "auto|user",
          'created_at': iso_datetime,
          'updated_at': iso_datetime
        }
    """

    def __init__(self,
                 config_path: Optional[str] = None,
                 db_path: Optional[str] = None,
                 legacy_artists_json: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent / "config.json"
        if db_path is None:
            db_path = Path(__file__).parent / "artists_db.json"
        if legacy_artists_json is None:
            legacy_artists_json = Path(__file__).parent / "artists.json"

        logger.info(f"配置文件: {config_path}")
        logger.info(f"数据库文件: {db_path}")

        self.config_path = Path(config_path)
        self.db_path = Path(db_path)
        self.legacy_artists_json = Path(legacy_artists_json)

        self.config = self._load_json_config(self.config_path)
        if not self.config:
            logger.info("创建默认配置 config.json")
            self.config = self._create_default_config()
            self._save_json_config(self.config, self.config_path)

        # 强制使用 UTF-8 防止 Windows 默认 gbk 编码问题
        self.db = TinyDB(self.db_path, ensure_ascii=False, indent=2, encoding='utf-8')
        self.table = self.db.table('artists')

        # 迁移旧 JSON 数据 (一次性)
        if self.legacy_artists_json.exists() and len(self.table) == 0:
            try:
                data = self._load_json_config(self.legacy_artists_json)
                auto_data = data.get('auto_detected', {}) if isinstance(data, dict) else {}
                user_data = data.get('user_defined', {}) if isinstance(data, dict) else {}
                inserted = 0
                for folder, names in auto_data.items():
                    self._upsert_record(folder=folder, names=names, category='auto', source='auto')
                    inserted += 1
                for names, folder in user_data.items():
                    # user_defined 原结构 names 是字符串 (可能包含空格分隔)
                    name_list = [n.strip() for n in names.split() if n.strip()]
                    self._upsert_record(folder=folder, names=name_list, category='auto', source='user')
                    inserted += 1
                logger.info(f"迁移旧 JSON 数据完成，共导入 {inserted} 条")
            except Exception as e:
                logger.error(f"旧数据迁移失败: {e}")

        self.base_dir = Path(self.config['paths']['base_dir'])
        if not self.base_dir.exists():
            logger.warning(f"基础目录不存在: {self.base_dir}")
        else:
            logger.info(f"基础目录: {self.base_dir}")

    # ---------------- Core helpers -----------------
    def _now(self) -> str:
        return datetime.now().isoformat()

    def _load_json_config(self, config_path: str) -> dict:
        """加载 JSON 配置文件"""
        if not os.path.exists(config_path):
            logger.warning(f"配置文件不存在: {config_path}")
            return {}
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 文件格式错误: {config_path} - {str(e)}")
            return {}
        except Exception as e:
            logger.error(f"读取配置文件失败: {config_path} - {str(e)}")
            return {}

    def _create_default_config(self) -> dict:
        """创建默认配置"""
        return {
            "paths": {
                "base_dir": "E:\\1EHV",
                "found_artists_dir": "E:\\1EHV\\[01已找到画师]"
            },
            "categories": {
                "CG": ["CG", "cg"],
                "漫画": ["漫画", "manga", "comic"],
                "插画": ["插画", "illust", "illustration"],
                "同人": ["同人", "doujin"],
                "原创": ["原创", "original"]
            },
            "exclude_keywords": [
                "汉化", "翻译", "Chinese", "中文", "简体", "繁体",
                "DL版", "无修正", "有修正", "高画质", "高清",
                ".zip", ".rar", ".7z"
            ]
        }
    
    def _create_default_artists_data(self) -> dict:
        """创建默认画师数据结构"""
        return {
            "metadata": {
                "version": "1.0.0",
                "created_time": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "auto_detected_count": 0,
                "user_defined_count": 0,
                "total_artists": 0,
                "description": "画师数据库 - 自动生成"
            },
            "auto_detected": {},
            "user_defined": {}
        }

    def _save_json_config(self, data: dict, config_path: str):
        """保存 JSON 配置文件"""
        # 更新时间戳
        if 'metadata' in data:
            data['metadata']['last_updated'] = datetime.now().isoformat()
        elif 'last_updated' in data:
            data['last_updated'] = datetime.now().isoformat()
            
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # -------------- DB Operations ------------------
    def _upsert_record(self, folder: str, names: List[str], category: str, source: str):
        q = Query()
        existing = self.table.get(q.folder == folder)
        now = self._now()
        if existing:
            update_fields = {
                'names': names,
                'category': category or existing.get('category', 'auto'),
                'source': source or existing.get('source', 'auto'),
                'updated_at': now
            }
            self.table.update(update_fields, q.folder == folder)
            logger.debug(f"更新记录: {folder} -> {names} ({category})")
        else:
            record = {
                'folder': folder,
                'names': names,
                'category': category or 'auto',
                'source': source or 'auto',
                'created_at': now,
                'updated_at': now
            }
            self.table.insert(record)
            logger.debug(f"插入新记录: {folder} -> {names} ({category})")

    # -------------- Public API ---------------------
    def scan_folder(self, path: Optional[str] = None, category: str = 'auto') -> int:
        """扫描指定文件夹下的画师目录并写入/更新数据库

        Returns: 新增或更新的数量
        """
        if path is None:
            path = str(self.base_dir)
        scan_path = Path(path)
        if not scan_path.exists():
            logger.error(f"扫描路径不存在: {scan_path}")
            return 0
        folders = [f.name for f in scan_path.iterdir() if f.is_dir() and f.name.startswith('[')]
        count = 0
        for folder_name in folders:
            clean_name = folder_name[1:-1] if folder_name.endswith(']') else folder_name[1:]
            names: List[str] = []
            if '(' in clean_name:
                circle_part = clean_name.split('(')[0].strip()
                artist_part = clean_name.split('(')[1].rstrip(')').strip()
                artist_names = [n.strip() for n in artist_part.split('、') if n.strip()]
                circle_names = [n.strip() for n in circle_part.split('、') if n.strip()]
                names.extend(artist_names + circle_names)
            else:
                names = [clean_name]
            # 过滤 exclude
            valid_names = [n for n in names if not any(k in n for k in self.config['exclude_keywords'])]
            if not valid_names:
                continue
            self._upsert_record(folder=folder_name, names=valid_names, category=category, source='auto')
            count += 1
        logger.info(f"扫描完成: {scan_path} -> {count} 条记录 (category={category})")
        return count

    def add_manual(self, names: List[str], folder: str, category: str):
        self._upsert_record(folder=folder, names=names, category=category, source='user')
        logger.info(f"已添加/更新手动条目: {folder} -> {names} ({category})")

    def set_category(self, name_or_folder: str, category: str) -> bool:
        q = Query()
        recs = self.table.search((q.folder == name_or_folder) | (q.names.any([name_or_folder])))
        if not recs:
            logger.warning(f"未找到条目: {name_or_folder}")
            return False
        for r in recs:
            self.table.update({'category': category, 'updated_at': self._now()}, Query().folder == r['folder'])
        logger.info(f"已更新 {len(recs)} 条分类 -> {category}")
        return True

    def list_category(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        if category in (None, 'all'):
            return self.table.all()
        q = Query()
        return self.table.search(q.category == category)

    def search(self, keyword: str) -> List[Dict[str, Any]]:
        q = Query()
        kw = keyword.lower()
        rows = self.table.search(
            (q.folder.test(lambda v: kw in v.lower())) |
            (q.names.any([keyword])) |
            (q.names.test(lambda arr: any(kw in n.lower() for n in arr)))
        )
        return rows

    def remove(self, name_or_folder: str) -> int:
        q = Query()
        removed = self.table.remove((q.folder == name_or_folder) | (q.names.any([name_or_folder])))
        logger.info(f"删除 {len(removed)} 条")
        return len(removed)

    def export_category(self, category: Optional[str], out_file: Path):
        rows = self.list_category(category)
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        logger.info(f"已导出 {len(rows)} 条 -> {out_file}")

    # ---------------- Formatting -------------------
    def format_rows(self, rows: List[Dict[str, Any]], fmt: str = 'table') -> str:
        if fmt == 'json':
            return json.dumps(rows, ensure_ascii=False, indent=2)
        names_only: List[str] = []
        for r in rows:
            names_only.extend(r.get('names', []))
        if fmt == 'names':
            return '\n'.join(sorted(set(names_only)))
        # table (简易)
        lines = [f"{'FOLDER':30} | CATEGORY | NAMES"]
        for r in rows:
            lines.append(f"{r['folder'][:30]:30} | {r['category']:<8} | {','.join(r['names'])}")
        return '\n'.join(lines)


def main():
    """主函数 - TinyDB 版 CLI"""
    import argparse

    parser = argparse.ArgumentParser(description="画师信息维护工具 (TinyDB)")
    parser.add_argument('--config', '-c', help='配置文件路径', default=None)
    parser.add_argument('--db', help='数据库文件路径 (TinyDB JSON)', default=None)

    sub = parser.add_subparsers(dest='command')

    # scan
    p_scan = sub.add_parser('scan', help='扫描目录生成/更新画师列表')
    p_scan.add_argument('--path', '-p', help='扫描路径，不传则用配置中的 base_dir')
    p_scan.add_argument('--clipboard', action='store_true', help='从剪贴板读取路径')
    p_scan.add_argument('--category', default='auto', help='扫描结果分类 (默认 auto)')

    # add
    p_add = sub.add_parser('add', help='手动添加/更新一个条目')
    p_add.add_argument('--names', '-n', required=True, help='逗号或空格分隔的多个名称')
    p_add.add_argument('--folder', '-f', required=True, help='文件夹原名 (含中括号)')
    p_add.add_argument('--category', '-g', default='auto', help='分类: white/black/其它自定义')

    # set-category
    p_set = sub.add_parser('set', help='修改某条目的分类')
    p_set.add_argument('--target', '-t', required=True, help='名称或文件夹名')
    p_set.add_argument('--category', '-g', required=True, help='新的分类')

    # list
    p_list = sub.add_parser('list', help='列出分类下的画师')
    p_list.add_argument('--category', '-g', default='all', help='分类 (white/black/auto/自定义/all)')
    p_list.add_argument('--format', '-F', choices=['table','names','json'], default='table', help='输出格式')
    p_list.add_argument('--copy', action='store_true', help='复制到剪贴板')

    # search
    p_search = sub.add_parser('search', help='搜索关键字')
    p_search.add_argument('--keyword', '-k', required=True)
    p_search.add_argument('--format', '-F', choices=['table','names','json'], default='table')
    p_search.add_argument('--copy', action='store_true')

    # remove
    p_rm = sub.add_parser('remove', help='按名称或文件夹删除')
    p_rm.add_argument('--target', '-t', required=True)

    # export
    p_exp = sub.add_parser('export', help='导出分类到文件')
    p_exp.add_argument('--category', '-g', default='all')
    p_exp.add_argument('--out', '-o', required=True)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        manager = ArtistInfoManager(config_path=args.config, db_path=args.db)

        if args.command == 'scan':
            scan_path = args.path
            if args.clipboard:
                clip = pyperclip.paste().strip()
                if clip:
                    scan_path = clip
                    logger.info(f"使用剪贴板路径: {scan_path}")
            manager.scan_folder(path=scan_path, category=args.category)

        elif args.command == 'add':
            raw = args.names.replace('，', ',')
            parts = [p.strip() for p in raw.replace(',', ' ').split() if p.strip()]
            manager.add_manual(parts, args.folder, args.category)

        elif args.command == 'set':
            manager.set_category(args.target, args.category)

        elif args.command == 'list':
            rows = manager.list_category(args.category)
            out_text = manager.format_rows(rows, args.format)
            _safe_print(out_text)
            if args.copy:
                pyperclip.copy(out_text)
                logger.info("结果已复制到剪贴板")

        elif args.command == 'search':
            rows = manager.search(args.keyword)
            out_text = manager.format_rows(rows, args.format)
            _safe_print(out_text)
            if args.copy:
                pyperclip.copy(out_text)
                logger.info("搜索结果已复制到剪贴板")

        elif args.command == 'remove':
            manager.remove(args.target)

        elif args.command == 'export':
            manager.export_category(args.category, Path(args.out))

    except Exception as e:
        logger.error(f"执行失败: {e}")
        raise


if __name__ == "__main__":
    main()

