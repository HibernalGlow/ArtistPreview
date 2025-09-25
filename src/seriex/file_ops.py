"""File-system helpers for seriex extraction workflows."""

from __future__ import annotations

import os
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from .grouping import SeriesGroupingEngine
from .utils import (
    SERIES_PREFIXES,
    is_series_blacklisted,
    is_supported_file,
)


def safe_move(src: str, dst: str, logger, max_retries: int = 2) -> str:
    """Move file safely by avoiding overwrites and handling cross-device moves."""
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        base, ext = os.path.splitext(dst)
        candidate = dst
        idx = 1
        while os.path.exists(candidate):
            candidate = f"{base}_{idx}{ext}"
            idx += 1
        try:
            shutil.move(src, candidate)
            return candidate
        except Exception:
            for attempt in range(max_retries + 1):
                try:
                    shutil.copy2(src, candidate)
                    os.remove(src)
                    return candidate
                except Exception as exc:
                    if attempt >= max_retries:
                        raise exc
    except Exception as exc:
        logger.error("移动失败: %s -> %s: %s", os.path.basename(src), dst, exc)
        raise


def collect_items_for_series(
    directory_path: str,
    config: dict,
    category_folders: Iterable[str],  # 保留签名兼容
    logger,
    dry_run: bool = False,
) -> tuple[list[str], list[str]]:
    base_level = len(Path(directory_path).parts)
    items: list[str] = []
    corrupted: list[str] = []
    for root, _, files in os.walk(directory_path):
        current_level = len(Path(root).parts)
        if current_level - base_level > 1:
            continue
        current_dir = os.path.basename(root)
        if current_dir.startswith('[#s]') or current_dir == "损坏压缩包":
            continue
        for file in files:
            if is_supported_file(file, config):
                file_path = os.path.join(root, file)
                if is_series_blacklisted(file):
                    logger.warning("文件在系列提取黑名单中，跳过: %s", file)
                    continue
                items.append(file_path)
    return items, corrupted


def create_series_folders(
    directory_path: str,
    files: list[str],
    *,
    config: dict,
    grouping_engine: SeriesGroupingEngine,
    logger,
    add_prefix: bool | None = None,
) -> dict[str, dict[str, list[str]]]:
    dir_groups = defaultdict(list)
    summary: dict[str, dict[str, list[str]]] = {}
    use_prefix = add_prefix if add_prefix is not None else config.get("add_prefix", True)
    creation_prefix = config.get("prefix", "[#s]") if use_prefix else ""
    files = [f for f in files if os.path.isfile(f)]

    for fp in files:
        dir_path = os.path.dirname(fp)
        parent_name = os.path.basename(dir_path)
        if any(parent_name.startswith(prefix) for prefix in SERIES_PREFIXES):
            continue
        dir_groups[dir_path].append(fp)

    allow_single = bool(config.get("known_series_allow_single", True))

    for dir_path, dir_archives in dir_groups.items():
        if len(dir_archives) <= 1:
            continue
        logger.info("找到 %d 个候选文件", len(dir_archives))
        series_groups = grouping_engine.find_series_groups(dir_archives)
        if not series_groups:
            continue
        logger.info("找到 %d 个系列", len(series_groups))
        series_folders: dict[str, str] = {}
        summary.setdefault(dir_path, {})
        for series_name, grouped_files in series_groups.items():
            if series_name == "其他":
                logger.warning("%d 个文件未能匹配到系列", len(grouped_files))
                continue
            if len(grouped_files) <= 1 and not (
                allow_single and grouping_engine.registry.contains(series_name)
            ):
                logger.warning(
                    "系列 '%s' 只有一个文件，且非参考系列或未启用单文件策略，跳过创建文件夹",
                    series_name,
                )
                continue
            folder_name = f"{creation_prefix}{series_name.strip()}"
            series_folder = os.path.join(dir_path, folder_name)
            if not os.path.exists(series_folder):
                os.makedirs(series_folder, exist_ok=True)
                logger.info("创建系列文件夹: %s", folder_name)
            series_folders[series_name] = series_folder
        for series_name, folder_path in series_folders.items():
            grouped_files = series_groups[series_name]
            logger.info("开始移动系列 '%s' 的文件...", series_name)
            moved_list: list[str] = []
            for file_path in grouped_files:
                target_path = os.path.join(folder_path, os.path.basename(file_path))
                try:
                    final_path = safe_move(file_path, target_path, logger)
                    logger.info(
                        "  └─ 移动: %s -> %s",
                        os.path.basename(file_path),
                        os.path.basename(final_path),
                    )
                    moved_list.append(os.path.basename(final_path))
                except Exception:
                    logger.warning("移动失败，已跳过: %s", os.path.basename(file_path))
            final_folder_name = os.path.basename(folder_path)
            if moved_list:
                summary[dir_path].setdefault(final_folder_name, []).extend(moved_list)
        logger.info("系列提取完成")
        logger.info("目录处理完成: %s", dir_path)
    return summary


def compute_series_plan(
    directory_path: str,
    files: list[str],
    *,
    config: dict,
    grouping_engine: SeriesGroupingEngine,
    logger,
    add_prefix: bool | None = None,
) -> dict[str, dict[str, list[str]]]:
    dir_groups = defaultdict(list)
    summary: dict[str, dict[str, list[str]]] = {}
    use_prefix = add_prefix if add_prefix is not None else config.get("add_prefix", True)
    creation_prefix = config.get("prefix", "[#s]") if use_prefix else ""
    files = [f for f in files if os.path.isfile(f)]

    for fp in files:
        dir_path = os.path.dirname(fp)
        parent_name = os.path.basename(dir_path)
        if any(parent_name.startswith(prefix) for prefix in SERIES_PREFIXES):
            continue
        dir_groups[dir_path].append(fp)

    allow_single = bool(config.get("known_series_allow_single", True))

    for dir_path, dir_archives in dir_groups.items():
        if len(dir_archives) <= 1:
            continue
        series_groups = grouping_engine.find_series_groups(dir_archives)
        if not series_groups:
            continue
        total_files = len(dir_archives)
        plan_for_dir: dict[str, list[str]] = {}
        for series_name, files_in_series in series_groups.items():
            if series_name == "其他":
                continue
            if len(files_in_series) <= 1 and not (
                allow_single and grouping_engine.registry.contains(series_name)
            ):
                continue
            if len(files_in_series) == total_files:
                plan_for_dir = {}
                break
            folder_name = f"{creation_prefix}{series_name.strip()}"
            plan_for_dir[folder_name] = list(files_in_series)
        if plan_for_dir:
            summary[dir_path] = plan_for_dir
    return summary


def move_corrupted_archive(file_path: str, base_path: str, logger) -> None:
    try:
        rel_path = os.path.relpath(os.path.dirname(file_path), base_path)
        corrupted_base = os.path.join(base_path, "损坏压缩包")
        target_dir = os.path.join(corrupted_base, rel_path)
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, os.path.basename(file_path))
        if os.path.exists(target_path):
            base, ext = os.path.splitext(target_path)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}"):
                counter += 1
            target_path = f"{base}_{counter}{ext}"
        shutil.move(file_path, target_path)
        logger.info(
            "已移动损坏压缩包: %s -> 损坏压缩包/%s",
            os.path.basename(file_path),
            rel_path,
        )
    except Exception as exc:
        logger.error("移动损坏压缩包失败 %s: %s", file_path, exc)


def update_series_folder_name(
    old_path: str,
    creation_prefix: str,
    grouping_engine: SeriesGroupingEngine,
    logger,
) -> bool:
    try:
        dir_name = os.path.basename(old_path)
        prefix_used = None
        for prefix in SERIES_PREFIXES:
            if dir_name.startswith(prefix):
                prefix_used = prefix
                break
        if not prefix_used:
            return False
        old_series_name = dir_name[len(prefix_used):]
        new_series_name = grouping_engine.get_series_key(old_series_name)
        if not new_series_name or new_series_name == old_series_name:
            return False
        new_prefix = creation_prefix or ""
        new_path = os.path.join(os.path.dirname(old_path), f"{new_prefix}{new_series_name}")
        if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(old_path):
            return False
        os.rename(old_path, new_path)
        return True
    except Exception as exc:
        logger.error("更新系列文件夹名称失败 %s: %s", old_path, exc)
        return False


def update_all_series_folders(
    directory_path: str,
    creation_prefix: str,
    grouping_engine: SeriesGroupingEngine,
    logger,
) -> int:
    try:
        updated_count = 0
        for root, dirs, _ in os.walk(directory_path):
            for dir_name in dirs:
                if any(dir_name.startswith(pfx) for pfx in SERIES_PREFIXES):
                    full_path = os.path.join(root, dir_name)
                    if update_series_folder_name(full_path, creation_prefix, grouping_engine, logger):
                        updated_count += 1
        if updated_count > 0:
            logger.info("更新了 %d 个系列文件夹名称", updated_count)
        return updated_count
    except Exception as exc:
        logger.error("更新系列文件夹失败: %s", exc)
        return 0
