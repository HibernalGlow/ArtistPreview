"""Registry for known series directories and names."""

from __future__ import annotations

import os
import threading
from typing import Iterable, List, Set

from .utils import SERIES_PREFIXES


class KnownSeriesRegistry:
    """Maintain a set of known series names discovered from reference folders."""

    def __init__(self, logger=None) -> None:
        self._known_series: Set[str] = set()
        self._processed_dirs: Set[str] = set()
        self._lock = threading.Lock()
        self._runtime_dirs: List[str] = []
        self._logger = logger

    @staticmethod
    def _strip_prefix(series_name: str) -> str:
        base = series_name
        for prefix in SERIES_PREFIXES:
            if base.startswith(prefix):
                base = base[len(prefix):]
                break
        return base.strip()

    def contains(self, series_name: str) -> bool:
        if not series_name:
            return False
        base = self._strip_prefix(series_name)
        return bool(base) and base in self._known_series

    def load_from_dirs(self, dirs: Iterable[str]) -> None:
        with self._lock:
            for root in dirs:
                if not root:
                    continue
                abs_root = os.path.abspath(root)
                if abs_root in self._processed_dirs:
                    continue
                if not os.path.isdir(abs_root):
                    self._processed_dirs.add(abs_root)
                    continue
                try:
                    for name in os.listdir(abs_root):
                        full = os.path.join(abs_root, name)
                        if not os.path.isdir(full):
                            continue
                        base = self._strip_prefix(name)
                        if base:
                            self._known_series.add(base)
                    self._processed_dirs.add(abs_root)
                except Exception:
                    self._processed_dirs.add(abs_root)
                    if self._logger:
                        self._logger.debug(f"跳过无法读取的目录: {abs_root}")

    def bootstrap_from_config(self, dirs: Iterable[str]) -> None:
        dirs_list = [d for d in dirs if d]
        if not dirs_list:
            return
        self._runtime_dirs = list(dirs_list)
        self.load_from_dirs(dirs_list)

    def set_runtime_dirs(self, dirs: Iterable[str]) -> None:
        self._runtime_dirs = [d for d in dirs if d]
        if self._runtime_dirs:
            self.load_from_dirs(self._runtime_dirs)

    def get_runtime_dirs(self) -> List[str]:
        return list(self._runtime_dirs)

    def snapshot(self) -> Set[str]:
        return set(self._known_series)
