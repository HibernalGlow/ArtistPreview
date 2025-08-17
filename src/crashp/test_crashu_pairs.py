#!/usr/bin/env python3
"""PairManager 配套测试

涵盖:
1. build_pairs 自动/手动模式 target_path 构造
2. save_pairs_to_json 写入文件
3. move_contents 三种冲突策略核心路径 (实际详细测试 skip/rename/overwrite 中两种代表)

运行: python test_crashu_pairs.py  或  pytest -q (若已安装 pytest)
"""
from __future__ import annotations

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

# 保证可导入 src 下包
ROOT = Path(__file__).parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crashp import PairManager  # noqa: E402


def _make_file(path: Path, text: str = "data"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_build_and_json_and_move():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        # 构造源与目标结构
        src_root = base / "src_root"
        tgt_root = base / "tgt_root"
        dst_manual = base / "manual_dst"
        src_root.mkdir()
        tgt_root.mkdir()
        dst_manual.mkdir()

        # 源子目录 (source_to_target 方向)
        src_sub = src_root / "ArtistA"
        src_sub.mkdir()
        _make_file(src_sub / "a.txt", "hello")

        # 目标目录 (auto_get 情况下的 target_fullpath)
        target_full = tgt_root / "Artist_A_Full"
        target_full.mkdir()
        _make_file(target_full / "exist.txt", "old")

        # 模拟 similar_folders (auto_get=True)
        similar_auto = [
            {
                "name": "ArtistA",
                "path": str(src_sub),
                "target": "Artist_A_Full",  # 名称
                "similarity": 0.95,
                "target_fullpath": str(target_full),
            }
        ]
        pairs_auto = PairManager.build_pairs(similar_auto, auto_get=True, destination_path=str(dst_manual))
        assert pairs_auto[0].target_path == str(target_full)

        # 保存 JSON
        json_path = base / "pairs.json"
        PairManager.save_pairs_to_json(pairs_auto, str(json_path))
        assert json_path.exists(), "JSON 文件未生成"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data[0]["source_name"] == "ArtistA"

        # 执行移动 (source_to_target, conflict=rename)
        # 制造冲突: 在目标放一个同名 a.txt
        _make_file(target_full / "a.txt", "old-a")
        result = PairManager.move_contents(pairs_auto, direction="source_to_target", conflict="rename", dry_run=False)
        # a.txt 应该被重命名移动过去, 原源目录应被清空/删除
        assert result.moved_files >= 1
        assert not src_sub.exists() or not any(src_sub.iterdir())
        # 确认目标仍有原 a.txt
        assert (target_full / "a.txt").exists()
        # 存在重命名文件
        renamed_candidates = list(target_full.glob("a_dup*"))
        assert renamed_candidates, "重命名文件未出现"

        # 再测试手动模式 build_pairs (auto_get=False)
        # 重新准备源结构
        src_sub2 = src_root / "ArtistB"
        src_sub2.mkdir(exist_ok=True)
        _make_file(src_sub2 / "b.txt", "bbb")
        similar_manual = [
            {
                "name": "ArtistB",
                "path": str(src_sub2),
                "target": "TargetGroup",
                "similarity": 0.9,
            }
        ]
        pairs_manual = PairManager.build_pairs(similar_manual, auto_get=False, destination_path=str(dst_manual))
        # 期望 target_path = manual_dst/TargetGroup/ArtistB
        expect_manual_target = dst_manual / "TargetGroup" / "ArtistB"
        assert pairs_manual[0].target_path == str(expect_manual_target)

        # overwrite 策略: 先在 target 放置同名文件, 确认被覆盖
        expect_manual_target.mkdir(parents=True, exist_ok=True)
        _make_file(expect_manual_target / "b.txt", "old-b")
        res_over = PairManager.move_contents(pairs_manual, direction="source_to_target", conflict="overwrite", dry_run=False)
        assert res_over.overwritten >= 1
        # 文件内容被替换
        content = (expect_manual_target / "b.txt").read_text(encoding="utf-8")
        assert content == "bbb"

    print("PairManager 测试完成 ✅")


if __name__ == "__main__":
    test_build_and_json_and_move()
