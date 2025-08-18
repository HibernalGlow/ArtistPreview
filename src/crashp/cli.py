"""crashp 交互式 JSON 配对移动工具

用法：
  1) 先通过 crashu 生成配对 JSON (folder_pairs.json)
  2) 运行: python -m crashp  或 安装后 `crashp`
  3) 按提示输入/确认 JSON 路径与移动选项

也可命令行快速执行:
  crashp path/to/pairs.json --dir 1 --conflict skip --dry-run

--dir 1 -> source_to_target ; --dir 2 -> target_to_source
"""
from __future__ import annotations

import argparse
import json
import os
from typing import List
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table

from . import PairManager, PairRecord  # type: ignore

console = Console()


def load_pairs_from_json(path: str) -> List[PairRecord]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    pairs: List[PairRecord] = []
    for item in data:
        # 兼容字段命名 (源 JSON 由 PairRecord.__dict__ 导出)
        pairs.append(
            PairRecord(
                source_name=item["source_name"],
                source_path=item["source_path"],
                target_name=item["target_name"],
                target_path=item["target_path"],
                similarity=float(item.get("similarity", 0.0)),
            )
        )
    return pairs


def show_pairs_preview(pairs: List[PairRecord], limit: int = 10):
    table = Table(title=f"配对预览 (前 {min(limit, len(pairs))} / 共 {len(pairs)})")
    table.add_column("#", justify="right")
    table.add_column("源名称")
    table.add_column("源路径", overflow="fold")
    table.add_column("目标名称")
    table.add_column("目标路径", overflow="fold")
    table.add_column("相似度", justify="right")
    for i, p in enumerate(pairs[:limit], 1):
        table.add_row(str(i), p.source_name, p.source_path, p.target_name, p.target_path, f"{p.similarity:.2f}")
    console.print(table)


def parse_args():
    parser = argparse.ArgumentParser(description="从配对 JSON 执行内容移动")
    parser.add_argument("json", nargs="?", help="配对 JSON 路径")
    parser.add_argument("--dir", choices=["1", "2", "source_to_target", "target_to_source"], help="移动方向 (1=源->目标 2=目标->源)")
    parser.add_argument("--conflict", choices=["skip", "overwrite", "rename"], help="冲突策略")
    parser.add_argument("--dry-run", action="store_true", help="只模拟不实际移动")
    parser.add_argument("--no-preview", action="store_true", help="不显示配对预览表")
    return parser.parse_args()


def choose_direction(arg_dir: str | None) -> str:
    mapping = {"1": "source_to_target", "2": "target_to_source"}
    if arg_dir:
        if arg_dir in mapping:
            return mapping[arg_dir]
        return arg_dir  # 已经是字符串形式
    choice = Prompt.ask("选择移动方向 (1=源->目标 2=目标->源)", choices=["1", "2"], default="1")
    return mapping[choice]


def choose_conflict(arg_conflict: str | None) -> str:
    if arg_conflict:
        return arg_conflict
    return Prompt.ask("冲突策略 (skip=跳过 overwrite=覆盖 rename=改名)", choices=["skip", "overwrite", "rename"], default="skip")


def main():
    args = parse_args()

    json_path = args.json or Prompt.ask("请输入配对 JSON 路径", default="folder_pairs.json")
    if not os.path.isfile(json_path):
        console.print(f"[red]文件不存在: {json_path}[/red]")
        return

    pairs = load_pairs_from_json(json_path)
    if not pairs:
        console.print("[yellow]JSON 中没有配对数据[/yellow]")
        return

    if not args.no_preview:
        show_pairs_preview(pairs)

    direction = choose_direction(args.dir)
    conflict = choose_conflict(args.conflict)

    if not args.dry_run:
        console.print(f"[cyan]执行移动: {direction} 冲突策略: {conflict}[/cyan]")
        proceed = Confirm.ask("确认执行移动?", default=True)
        if not proceed:
            console.print("[yellow]已取消[/yellow]")
            return
    else:
        console.print(f"[cyan]Dry Run 模式: 仅模拟 {direction} {conflict}[/cyan]")

    result = PairManager.move_contents(
        pairs,
        direction=direction,  # type: ignore
        conflict=conflict,    # type: ignore
        dry_run=args.dry_run,
    )

    # 输出结果
    stats = result.as_dict()
    table = Table(title="移动结果统计")
    table.add_column("指标")
    table.add_column("数量", justify="right")
    for k, v in stats.items():
        table.add_row(k, str(v))
    console.print(table)

    console.print("[green]完成[/green]")


if __name__ == "__main__":
    main()
