"""配对与内容移动管理

输入：来自 crashu 的 similar_folders 列表（每项包含 name,path,target,similarity 以及可选 target_fullpath）
输出：标准化的配对结构 + JSON 记录 + 内容移动。
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from typing import Iterable, List, Literal


@dataclass
class PairRecord:
    source_name: str
    source_path: str
    target_name: str
    target_path: str
    similarity: float


@dataclass
class PairMoveResult:
    moved_files: int = 0
    skipped_conflicts: int = 0
    overwritten: int = 0
    renamed: int = 0
    pairs_processed: int = 0

    def as_dict(self):  # 方便序列化/打印
        return {
            "pairs_processed": self.pairs_processed,
            "moved_files": self.moved_files,
            "skipped_conflicts": self.skipped_conflicts,
            "overwritten": self.overwritten,
            "renamed": self.renamed,
        }


ConflictPolicy = Literal["skip", "overwrite", "rename"]
MoveDirection = Literal["source_to_target", "target_to_source"]


class PairManager:
    @staticmethod
    def build_pairs(
        similar_folders: Iterable[dict],
        auto_get: bool,
        destination_path: str,
    ) -> List[PairRecord]:
        """标准化 similar_folders -> PairRecord 列表

        auto_get=True 时，target_fullpath 已给出；否则 target_path 由 destination_path/target/name 规则拼接（与原输出保持一致逻辑）。
        """
        pairs: List[PairRecord] = []
        for item in similar_folders:
            source_path = item["path"]
            if auto_get and item.get("target_fullpath"):
                target_path = item["target_fullpath"]
            else:
                # 手动模式：目标父目录 = destination_path/target_name ; 实际要合并的目标文件夹为父目录下与源同名
                target_path = os.path.join(destination_path, item["target"], item["name"])
            pairs.append(
                PairRecord(
                    source_name=item["name"],
                    source_path=source_path,
                    target_name=item["target"],
                    target_path=target_path,
                    similarity=float(item["similarity"]),
                )
            )
        return pairs

    @staticmethod
    def save_pairs_to_json(pairs: Iterable[PairRecord], json_path: str):
        data = [pair.__dict__ for pair in pairs]
        directory = os.path.dirname(json_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def move_contents(
        pairs: Iterable[PairRecord],
        direction: MoveDirection = "source_to_target",
        conflict: ConflictPolicy = "skip",
        dry_run: bool = False,
    ) -> PairMoveResult:
        """将配对文件夹的一方内容移动到另一方。

        direction: source_to_target 把 source_path 内容移入 target_path；target_to_source 反向。
        conflict:
          - skip: 目标已存在同名文件则跳过
          - overwrite: 覆盖（文件用 shutil.move 覆盖；若是目录，递归合并）
          - rename: 避冲突追加 _dup{n}
        dry_run: 仅统计不实际移动。
        """
        result = PairMoveResult()
        for pair in pairs:
            from_path = pair.source_path if direction == "source_to_target" else pair.target_path
            to_path = pair.target_path if direction == "source_to_target" else pair.source_path

            if not os.path.isdir(from_path):
                continue
            os.makedirs(to_path, exist_ok=True)

            for entry in os.listdir(from_path):
                src = os.path.join(from_path, entry)
                dst = os.path.join(to_path, entry)
                if os.path.exists(dst):
                    if conflict == "skip":
                        result.skipped_conflicts += 1
                        continue
                    elif conflict == "overwrite":
                        if not dry_run:
                            if os.path.isdir(dst) and os.path.isdir(src):
                                # 递归合并: 把 src 内内容移到 dst 内
                                for root, dirs, files in os.walk(src):
                                    rel = os.path.relpath(root, src)
                                    target_root = dst if rel == "." else os.path.join(dst, rel)
                                    os.makedirs(target_root, exist_ok=True)
                                    for f in files:
                                        shutil.move(os.path.join(root, f), os.path.join(target_root, f))
                                shutil.rmtree(src, ignore_errors=True)
                            else:
                                # 删除再移动
                                if os.path.isdir(dst):
                                    shutil.rmtree(dst, ignore_errors=True)
                                else:
                                    try:
                                        os.remove(dst)
                                    except OSError:
                                        pass
                                shutil.move(src, dst)
                        result.overwritten += 1
                        result.moved_files += 1
                    elif conflict == "rename":
                        if not dry_run:
                            base, ext = os.path.splitext(dst)
                            i = 1
                            new_dst = f"{base}_dup{i}{ext}"
                            while os.path.exists(new_dst):
                                i += 1
                                new_dst = f"{base}_dup{i}{ext}"
                            shutil.move(src, new_dst)
                        result.renamed += 1
                        result.moved_files += 1
                else:
                    if not dry_run:
                        shutil.move(src, dst)
                    result.moved_files += 1

            # 如果 from_path 已空，可尝试删除（忽略错误）
            if not dry_run:
                try:
                    if not os.listdir(from_path):
                        os.rmdir(from_path)
                except OSError:
                    pass
            result.pairs_processed += 1

        return result
