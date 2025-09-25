"""Series naming and grouping utilities for seriex."""

from __future__ import annotations

import difflib
import os
import re
from collections import defaultdict
from typing import Iterable, Sequence

from .known_series import KnownSeriesRegistry
from .similarity import SimilarityCalculator
from .utils import SERIES_PREFIXES, normalize_chinese


class SeriesGroupingEngine:
    """Encapsulates the logic for detecting and grouping related files into series."""

    def __init__(
        self,
        similarity: SimilarityCalculator,
        registry: KnownSeriesRegistry,
        config: dict,
        logger,
    ) -> None:
        self.similarity = similarity
        self.registry = registry
        self.config = config
        self.logger = logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def find_series_groups(self, filenames: Sequence[str]) -> dict[str, list[str]]:
        return _find_series_groups(filenames, self)

    def get_series_key(self, filename: str) -> str:
        return _get_series_key(filename, self)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    @staticmethod
    def preprocess_filename(filename: str) -> str:
        name = os.path.basename(filename)
        name = name.rsplit('.', 1)[0]
        for prefix in SERIES_PREFIXES:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        name = re.sub(r'\[.*?\]', '', name)
        name = re.sub(r'\(.*?\)', '', name)
        return ' '.join(name.split())

    @staticmethod
    def get_keywords(name: str) -> list[str]:
        return name.strip().split()

    @staticmethod
    def find_longest_common_keywords(keywords1: list[str], keywords2: list[str]) -> list[str]:
        matcher = difflib.SequenceMatcher(None, keywords1, keywords2)
        match = matcher.find_longest_match(0, len(keywords1), 0, len(keywords2))
        return keywords1[match.a:match.a + match.size]

    @staticmethod
    def validate_series_name(name: str) -> str | None:
        if not name or len(name) <= 1:
            return None
        name = normalize_chinese(name)
        name = re.sub(r'[\s.．。·・+＋\-－—_＿\d]+$', '', name)
        name = re.sub(r'[第章话集卷期篇季部册上中下前后完全][篇话集卷期章节部册全]*$', '', name)
        name = re.sub(r'(?i)vol\.?\s*\d*$', '', name)
        name = re.sub(r'(?i)volume\s*\d*$', '', name)
        name = re.sub(r'(?i)part\s*\d*$', '', name)
        name = name.strip()
        if re.search(r'(?i)comic', name):
            return None
        words = name.split()
        if all(len(word) <= 1 for word in words) and len(''.join(words)) <= 3:
            return None
        if not name or len(name) <= 1 or (len(name) > 0 and len(name.split()[-1]) <= 1):
            return None
        return name

    @staticmethod
    def get_base_filename(filename: str) -> str:
        name = os.path.splitext(filename)[0]
        name = re.sub(r'\[[^\]]*\]', '', name)
        name = re.sub(r'\([^)]*\)', '', name)
        name = re.sub(r'[\s!！?？_~～]+', '', name)
        name = normalize_chinese(name)
        return name


# ----------------------------------------------------------------------
# Internal helpers operating on SeriesGroupingEngine
# ----------------------------------------------------------------------

def _get_series_key(filename: str, engine: SeriesGroupingEngine) -> str:
    engine.logger.info(f"处理文件: {filename}")
    test_group = [filename, filename]
    series_groups = _find_series_groups(test_group, engine)
    if series_groups:
        series_name = next(iter(series_groups.keys()))
        engine.logger.info(f"找到系列名称: {series_name}")
        return series_name
    name = engine.preprocess_filename(filename)
    name = normalize_chinese(name)
    engine.logger.info(f"使用预处理结果: {name}")
    return name.strip()


def _find_series_groups(filenames: Sequence[str], engine: SeriesGroupingEngine) -> dict[str, list[str]]:
    logger = engine.logger
    registry = engine.registry
    config = engine.config

    processed_names = {f: engine.preprocess_filename(f) for f in filenames}
    processed_keywords = {f: SeriesGroupingEngine.get_keywords(processed_names[f]) for f in filenames}
    simplified_names = {f: normalize_chinese(n) for f, n in processed_names.items()}
    simplified_keywords = {
        f: [normalize_chinese(k) for k in kws]
        for f, kws in processed_keywords.items()
    }

    series_groups: dict[str, list[str]] = defaultdict(list)
    remaining_files = set(filenames)
    matched_files: set[str] = set()

    logger.info("预处理阶段：检查已标记的系列")
    for file_path in list(remaining_files):
        if file_path in matched_files:
            continue
        file_name = os.path.basename(file_path)
        for prefix in SERIES_PREFIXES:
            if file_name.startswith(prefix):
                series_name = file_name[len(prefix):]
                series_name = re.sub(r'\[.*?\]|\(.*?\)', '', series_name)
                series_name = series_name.strip()
                if series_name:
                    series_groups[series_name].append(file_path)
                    matched_files.add(file_path)
                    remaining_files.remove(file_path)
                    logger.info(
                        "预处理阶段：文件 '%s' 已标记为系列 '%s'",
                        os.path.basename(file_path),
                        series_name,
                    )
                break

    logger.info("优先阶段：准备加载已知系列目录配置...")
    runtime_dirs = registry.get_runtime_dirs()
    if runtime_dirs:
        registry.load_from_dirs(runtime_dirs)
    else:
        known_dirs = config.get("known_series_dirs", []) if isinstance(config, dict) else []
        if isinstance(known_dirs, list) and known_dirs:
            registry.load_from_dirs(known_dirs)

    known_series_set = registry.snapshot()
    logger.info(
        "优先阶段：已知系列名数量=%d，待处理文件数=%d",
        len(known_series_set),
        len(remaining_files),
    )

    if known_series_set and remaining_files:
        logger.info("优先阶段：匹配已知系列名（来自配置目录/运行时）")
        matched_by_known: dict[str, list[str]] = defaultdict(list)
        known_norm_pairs: list[tuple[str, str]] = []
        for s in known_series_set:
            s_norm = normalize_chinese(s)
            s_norm = re.sub(r"\s+", "", s_norm)
            if s_norm:
                known_norm_pairs.append((s_norm.lower(), s))
        known_norm_pairs.sort(key=lambda x: len(x[0]), reverse=True)
        for file in list(remaining_files):
            raw_name = os.path.basename(file)
            raw_name = raw_name.rsplit('.', 1)[0]
            base_name = normalize_chinese(raw_name)
            base_name_no_space = re.sub(r"\s+", "", base_name).lower()
            hit = None
            for s_norm, s_orig in known_norm_pairs:
                if s_norm and s_norm in base_name_no_space:
                    hit = s_orig
                    break
            if hit:
                matched_by_known[hit].append(file)
                matched_files.add(file)
                remaining_files.remove(file)
                logger.info(
                    "优先阶段：文件 '%s' 命中已知系列 '%s'（包含系列名）",
                    os.path.basename(file),
                    hit,
                )
        allow_single = True
        if isinstance(config, dict):
            allow_single = bool(config.get("known_series_allow_single", True))
        for series_name, files in matched_by_known.items():
            if len(files) > 1 or (allow_single and len(files) == 1):
                series_groups[series_name].extend(files)
                logger.info(
                    "优先阶段：将 %d 个文件加入已知系列 '%s'",
                    len(files),
                    series_name,
                )
    else:
        known_dirs = []
        if isinstance(config, dict):
            known_dirs = config.get("known_series_dirs", []) or []
        has_runtime = bool(runtime_dirs)
        if not known_dirs and not has_runtime:
            logger.info("优先阶段：未配置已知系列目录，跳过")
        elif known_dirs or has_runtime:
            logger.info("优先阶段：已配置已知系列目录但未发现可用的系列名，跳过")

    logger.info("第一阶段：风格匹配（关键词匹配）")
    while remaining_files:
        best_length = 0
        best_common = None
        best_pair = None
        best_series_name = None

        for file1 in remaining_files:
            if file1 in matched_files:
                continue
            keywords1 = simplified_keywords[file1]
            base_name1 = SeriesGroupingEngine.get_base_filename(os.path.basename(file1))
            for file2 in remaining_files - {file1}:
                if file2 in matched_files:
                    continue
                base_name2 = SeriesGroupingEngine.get_base_filename(os.path.basename(file2))
                if base_name1 == base_name2:
                    continue
                keywords2 = simplified_keywords[file2]
                common = SeriesGroupingEngine.find_longest_common_keywords(keywords1, keywords2)
                if common and len(common) > best_length:
                    series_name = SeriesGroupingEngine.validate_series_name(' '.join(common))
                    if series_name:
                        best_length = len(common)
                        best_common = common
                        best_pair = (file1, file2)
                        best_series_name = series_name

        if best_pair and best_series_name and best_common:
            matched_files_this_round = set(best_pair)
            base_name1 = SeriesGroupingEngine.get_base_filename(os.path.basename(best_pair[0]))
            for other_file in remaining_files - matched_files_this_round - matched_files:
                other_base_name = SeriesGroupingEngine.get_base_filename(os.path.basename(other_file))
                if base_name1 == other_base_name:
                    continue
                other_keywords = simplified_keywords[other_file]
                common = SeriesGroupingEngine.find_longest_common_keywords(
                    simplified_keywords[best_pair[0]], other_keywords
                )
                if common == best_common:
                    matched_files_this_round.add(other_file)
            series_groups[best_series_name].extend(matched_files_this_round)
            remaining_files -= matched_files_this_round
            matched_files.update(matched_files_this_round)
            logger.info("第一阶段：通过关键词匹配找到系列 '%s'", best_series_name)
            for file_path in matched_files_this_round:
                logger.info("  └─ %s", os.path.basename(file_path))
        else:
            break

    if remaining_files:
        logger.info("第二阶段：完全基础名匹配")
        existing_series = list(series_groups.keys())
        dir_path = os.path.dirname(list(remaining_files)[0]) if remaining_files else ''
        try:
            for folder_name in os.listdir(dir_path):
                if os.path.isdir(os.path.join(dir_path, folder_name)):
                    for prefix in SERIES_PREFIXES:
                        if folder_name.startswith(prefix):
                            series_name = folder_name[len(prefix):]
                            if series_name not in existing_series:
                                existing_series.append(series_name)
                                logger.info("第二阶段：从目录中找到已有系列 '%s'", series_name)
                            break
        except Exception:
            pass

        matched_files_by_series: dict[str, list[str]] = defaultdict(list)
        for file in list(remaining_files):
            if file in matched_files:
                continue
            base_name = simplified_names[file]
            base_name_no_space = re.sub(r'\s+', '', base_name)
            for series_name in existing_series:
                series_base = normalize_chinese(series_name)
                series_base_no_space = re.sub(r'\s+', '', series_base)
                if series_base_no_space in base_name_no_space:
                    base_name_current = SeriesGroupingEngine.get_base_filename(os.path.basename(file))
                    has_same_base = False
                    for existing_file in matched_files_by_series[series_name]:
                        if SeriesGroupingEngine.get_base_filename(os.path.basename(existing_file)) == base_name_current:
                            has_same_base = True
                            break
                    if not has_same_base:
                        matched_files_by_series[series_name].append(file)
                        matched_files.add(file)
                        remaining_files.remove(file)
                        logger.info(
                            "第二阶段：文件 '%s' 匹配到已有系列 '%s'（包含系列名）",
                            os.path.basename(file),
                            series_name,
                        )
                    break
        for series_name, files in matched_files_by_series.items():
            series_groups[series_name].extend(files)
            logger.info("第二阶段：将 %d 个文件添加到系列 '%s'", len(files), series_name)
            for file_path in files:
                logger.info("  └─ %s", os.path.basename(file_path))

    if remaining_files:
        logger.info("第三阶段：最长公共子串匹配")
        while remaining_files:
            best_ratio = 0
            best_pair = None
            best_common = None
            original_form = None
            for file1 in remaining_files:
                if file1 in matched_files:
                    continue
                base1 = simplified_names[file1]
                base1_lower = base1.lower()
                original1 = processed_names[file1]
                base_name1 = SeriesGroupingEngine.get_base_filename(os.path.basename(file1))
                for file2 in remaining_files - {file1}:
                    if file2 in matched_files:
                        continue
                    base_name2 = SeriesGroupingEngine.get_base_filename(os.path.basename(file2))
                    if base_name1 == base_name2:
                        continue
                    base2 = simplified_names[file2]
                    base2_lower = base2.lower()
                    matcher = difflib.SequenceMatcher(None, base1_lower, base2_lower)
                    ratio = matcher.ratio()
                    if ratio > best_ratio and ratio > 0.6:
                        best_ratio = ratio
                        best_pair = (file1, file2)
                        match = matcher.find_longest_match(0, len(base1_lower), 0, len(base2_lower))
                        best_common = base1_lower[match.a:match.a + match.size]
                        original_form = original1[match.a:match.a + match.size]
            if best_pair and best_common and original_form and len(best_common.strip()) > 1:
                matched_files_this_round = set(best_pair)
                base_name1 = SeriesGroupingEngine.get_base_filename(os.path.basename(best_pair[0]))
                for other_file in remaining_files - matched_files_this_round - matched_files:
                    other_base_name = SeriesGroupingEngine.get_base_filename(os.path.basename(other_file))
                    if base_name1 == other_base_name:
                        continue
                    other_base = simplified_names[other_file].lower()
                    if best_common in other_base:
                        matched_files_this_round.add(other_file)
                series_name = SeriesGroupingEngine.validate_series_name(original_form)
                if series_name:
                    series_groups[series_name].extend(matched_files_this_round)
                    remaining_files -= matched_files_this_round
                    matched_files.update(matched_files_this_round)
                    logger.info("第三阶段：通过公共子串匹配找到系列 '%s'", series_name)
                    logger.info("  └─ 公共子串：'%s' (相似度: %.2f%%)", best_common, best_ratio * 100)
                    for file_path in matched_files_this_round:
                        logger.info("  └─ 文件 '%s'", os.path.basename(file_path))
                else:
                    remaining_files.remove(best_pair[0])
                    matched_files.add(best_pair[0])
            else:
                break

    if remaining_files:
        logger.warning("还有 %d 个文件未能匹配到任何系列", len(remaining_files))

    return dict(series_groups)
