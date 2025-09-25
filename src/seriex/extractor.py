"""
高层系列提取调度模块
"""

from __future__ import annotations

import os
from typing import Optional

from .file_ops import (
    collect_items_for_series,
    compute_series_plan,
    create_series_folders,
    move_corrupted_archive,
    safe_move,
    update_all_series_folders,
)
from .grouping import SeriesGroupingEngine
from .known_series import KnownSeriesRegistry
from .similarity import SimilarityCalculator
from .utils import SERIES_PREFIXES, load_seriex_config, setup_logger


class SeriesExtractor:
    """系列提取器类，处理系列提取相关操作"""
    
    def __init__(
        self,
        similarity_config: Optional[dict] = None,
        config_path: Optional[str] = None,
        add_prefix: Optional[bool] = None,
    ) -> None:
        self.logger = setup_logger("seriex")
        self.config = load_seriex_config(config_path)
        self.add_prefix = add_prefix if add_prefix is not None else self.config.get("add_prefix", True)

        creation_prefix = self.config.get("prefix", "[#s]")
        if creation_prefix:
            SERIES_PREFIXES.add(creation_prefix)

        self.registry = KnownSeriesRegistry(logger=self.logger)
        known_dirs = self.config.get("known_series_dirs", []) if isinstance(self.config, dict) else []
        if isinstance(known_dirs, list) and known_dirs:
            self.registry.bootstrap_from_config(known_dirs)

        self.similarity = SimilarityCalculator(logger=self.logger)
        if similarity_config:
            self.similarity.update(similarity_config)

        self.grouping_engine = SeriesGroupingEngine(
            similarity=self.similarity,
            registry=self.registry,
            config=self.config,
            logger=self.logger,
        )

        self.last_summary: dict[str, dict[str, list[str]]] = {}
        self.last_plan: dict[str, dict[str, list[str]]] = {}
        self.last_corrupted: list[str] = []

    # ------------------------------------------------------------------
    # Registry / configuration management
    # ------------------------------------------------------------------
    def reload_known_series_dirs(self, dirs: list[str]) -> None:
        self.registry.set_runtime_dirs(dirs)

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------
    def process_directory(self, directory_path: str) -> bool:
        try:
            if not os.path.isdir(directory_path):
                self.logger.error("目录不存在或不是有效目录: %s", directory_path)
                return False

            if self.add_prefix:
                self.logger.info("检查并更新旧的系列文件夹名称...")
                creation_prefix = self.config.get("prefix", "[#s]")
                update_all_series_folders(
                    directory_path,
                    creation_prefix,
                    grouping_engine=self.grouping_engine,
                    logger=self.logger,
                )

            self.logger.info("开始查找可提取系列的文件（按配置扩展名）...")
            items, _ = collect_items_for_series(
                directory_path,
                self.config,
                [],
                logger=self.logger,
                dry_run=False,
            )

            if not items:
                self.logger.info("没有找到可提取系列的文件")
                return True

            self.logger.info("在目录及其子文件夹下找到 %d 个有效文件", len(items))
            self.last_summary = create_series_folders(
                directory_path,
                items,
                config=self.config,
                grouping_engine=self.grouping_engine,
                logger=self.logger,
                add_prefix=self.add_prefix,
            )
            self.logger.info("目录处理完成: %s", directory_path)
            return True
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.error("处理目录时出错: %s", exc)
            return False

    def prepare_directory(self, directory_path: str) -> dict[str, dict[str, list[str]]]:
        if not os.path.isdir(directory_path):
            self.logger.error("目录不存在或不是有效目录: %s", directory_path)
            return {}
        items, corrupted = collect_items_for_series(
            directory_path,
            self.config,
            [],
            logger=self.logger,
            dry_run=True,
        )
        self.last_corrupted = corrupted
        plan = compute_series_plan(
            directory_path,
            items,
            config=self.config,
            grouping_engine=self.grouping_engine,
            logger=self.logger,
            add_prefix=self.add_prefix,
        )
        self.last_plan = plan
        return plan

    def apply_prepared_plan(self, directory_path: str) -> dict[str, dict[str, list[str]]]:
        if not self.last_plan:
            self.logger.info("没有可执行的计划")
            return {}

        if self.config.get("check_integrity", True) and self.last_corrupted:
            for path in self.last_corrupted:
                move_corrupted_archive(path, directory_path, self.logger)

        summary: dict[str, dict[str, list[str]]] = {}
        for dir_path, folder_map in self.last_plan.items():
            summary.setdefault(dir_path, {})
            for folder_name, files in folder_map.items():
                series_folder = os.path.join(dir_path, folder_name)
                os.makedirs(series_folder, exist_ok=True)
                moved_list: list[str] = []
                for file_path in files:
                    target_path = os.path.join(series_folder, os.path.basename(file_path))
                    try:
                        final_path = safe_move(file_path, target_path, self.logger)
                        self.logger.info(
                            "  └─ 移动: %s -> %s",
                            os.path.basename(file_path),
                            os.path.basename(final_path),
                        )
                        moved_list.append(os.path.basename(final_path))
                    except Exception:
                        self.logger.warning("移动失败，已跳过: %s", os.path.basename(file_path))
                if moved_list:
                    summary[dir_path].setdefault(folder_name, []).extend(moved_list)
        self.last_summary = summary
        return summary


seriex = SeriesExtractor