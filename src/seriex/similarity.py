"""Utilities for computing string similarity for seriex."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Mapping, Optional

from .utils import normalize_chinese

try:  # pragma: no cover - runtime optional dependency
    from rapidfuzz import fuzz  # type: ignore
except Exception:  # pragma: no cover
    class _FuzzFallback:
        """Fallback implementation when rapidfuzz is unavailable."""

        @staticmethod
        def ratio(a: str, b: str) -> int:
            return int(difflib.SequenceMatcher(None, a, b).ratio() * 100)

        partial_ratio = ratio
        token_sort_ratio = ratio

    fuzz = _FuzzFallback()  # type: ignore


_SIMILARITY_KEYS = {
    "THRESHOLD": "threshold",
    "LENGTH_DIFF_MAX": "length_diff_max",
    "RATIO_THRESHOLD": "ratio_threshold",
    "PARTIAL_THRESHOLD": "partial_threshold",
    "TOKEN_THRESHOLD": "token_threshold",
}


@dataclass
class SimilarityConfig:
    """Container for similarity thresholds used by seriex."""

    threshold: int = 75
    length_diff_max: float = 0.3
    ratio_threshold: int = 75
    partial_threshold: int = 85
    token_threshold: int = 80

    @classmethod
    def from_mapping(cls, data: Optional[Mapping[str, float | int]]) -> "SimilarityConfig":
        if not data:
            return cls()
        kwargs: dict[str, float | int] = {}
        for key, attr in _SIMILARITY_KEYS.items():
            if key in data:
                kwargs[attr] = data[key]
        return cls(**kwargs)  # type: ignore[arg-type]

    def update_with_mapping(self, data: Optional[Mapping[str, float | int]]) -> None:
        if not data:
            return
        for key, attr in _SIMILARITY_KEYS.items():
            if key in data:
                setattr(self, attr, data[key])

    def to_mapping(self) -> dict[str, float | int]:
        return {key: getattr(self, attr) for key, attr in _SIMILARITY_KEYS.items()}


class SimilarityCalculator:
    """Wrapper around rapidfuzz for consistent similarity metrics."""

    def __init__(
        self,
        config: Optional[SimilarityConfig] = None,
        *,
        logger=None,
    ) -> None:
        self.config = config or SimilarityConfig()
        self.logger = logger

    def update(self, data: Optional[Mapping[str, float | int]]) -> None:
        self.config.update_with_mapping(data)

    def calculate(self, text_a: str, text_b: str) -> int:
        """Return max similarity score between two strings."""

        norm_a = normalize_chinese(text_a)
        norm_b = normalize_chinese(text_b)

        lower_a = norm_a.lower()
        lower_b = norm_b.lower()

        ratio = fuzz.ratio(lower_a, lower_b)
        partial = fuzz.partial_ratio(lower_a, lower_b)
        token = fuzz.token_sort_ratio(lower_a, lower_b)

        max_similarity = max(ratio, partial, token)
        if self.logger and max_similarity >= self.config.threshold:
            self.logger.info(f"相似度: {max_similarity}%")
        return max_similarity

    @property
    def threshold(self) -> int:
        return int(self.config.threshold)
