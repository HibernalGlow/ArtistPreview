from pathlib import Path

from seriex.extractor import SeriesExtractor
from seriex.known_series import KnownSeriesRegistry
from seriex.similarity import SimilarityCalculator


def test_similarity_calculator_basic():
    calc = SimilarityCalculator()
    score = calc.calculate("Amazing Series 01", "Amazing Series 02")
    assert score >= 70


def test_known_series_registry_loads(tmp_path):
    root = tmp_path / "library"
    series_dir = root / "[#s]My Series"
    series_dir.mkdir(parents=True)

    registry = KnownSeriesRegistry()
    registry.load_from_dirs([str(root)])

    assert registry.contains("[#s]My Series")
    assert registry.contains("My Series")


def test_series_extractor_plan_and_apply(tmp_path):
    file_a = tmp_path / "Amazing Series 01.zip"
    file_b = tmp_path / "Amazing Series 02.zip"
    file_c = tmp_path / "Standalone Work.zip"
    file_a.write_text("a")
    file_b.write_text("b")
    file_c.write_text("c")

    extractor = SeriesExtractor(add_prefix=True)

    plan = extractor.prepare_directory(str(tmp_path))
    assert plan, "expected plan to contain series grouping"

    summary = extractor.apply_prepared_plan(str(tmp_path))
    assert summary, "expected summary after applying plan"

    target_dir = tmp_path / "[#s]Amazing Series"
    assert target_dir.exists()
    moved_files = sorted(p.name for p in target_dir.iterdir())
    assert moved_files == sorted([file_a.name, file_b.name])
    assert file_c.exists()
