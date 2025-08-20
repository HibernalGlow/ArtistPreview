from __future__ import annotations
import sys
import os
import shutil
from pathlib import Path
import json
import subprocess
import shlex
import typer
import pyperclip
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
import re

app = typer.Typer(add_completion=False, help="搜索辅助工具：支持管道关键词 / 剪贴板路径 / 交互式 Rich")
console = Console()

DEFAULT_EXTS = [".jpg", ".png", ".jpeg", ".gif", ".webp", ".txt", ".md", ".json", ".zip", ".rar", ".7z"]


def detect_piped_input() -> str | None:
    if not sys.stdin.isatty():  # 有管道
        data = sys.stdin.read().strip()
        return data or None
    return None


def build_ripgrep_command(pattern: str, root: Path, files: bool, ignore_case: bool, glob: list[str] | None) -> list[str]:
    cmd = ["rg", "--no-heading", "--line-number"]
    if ignore_case:
        cmd.append("-i")
    if glob:
        for g in glob:
            cmd += ["-g", g]
    if files:
        cmd.append("--files-with-matches")
    cmd.append(pattern)
    cmd.append(str(root))
    return cmd


def run_ripgrep(cmd: list[str]) -> list[str]:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="ignore")
    except subprocess.CalledProcessError as e:  # 无结果时返回码 1
        if e.returncode == 1:
            return []
        raise
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    # 如果使用 --files-with-matches 则一行一个文件；否则行为 file:line:content
    return lines


def python_fallback_search(keywords: list[str], root: Path, exts: list[str] | None, files_only: bool, max_size_mb: int = 5) -> list[str]:
    kws = [k.lower() for k in keywords if k]
    if not kws:
        return []
    results: list[str] = []
    for p in root.rglob('*'):
        try:
            if not p.is_file():
                continue
            if exts and p.suffix and p.suffix.lower() not in exts:
                continue
            lower_name = p.name.lower()
            name_hit = any(k in lower_name for k in kws)
            snippet_added = False
            if name_hit:
                if files_only:
                    results.append(str(p))
                else:
                    results.append(str(p))  # 将真正的内容匹配放在后续
                continue
            # 内容匹配
            if p.stat().st_size <= max_size_mb * 1024 * 1024:
                try:
                    with p.open('r', encoding='utf-8', errors='ignore') as fh:
                        for line in fh:
                            l_low = line.lower()
                            if any(k in l_low for k in kws):
                                if files_only:
                                    results.append(str(p))
                                else:
                                    results.append(f"{p}:{line.strip()}")
                                snippet_added = True
                                break
                except Exception:
                    pass
            if snippet_added:
                continue
        except Exception:
            continue
    return results


def present_results(rows: list[str], keyword: str, as_table: bool, only_files: bool):
    if as_table:
        table = Table(title=f"搜索: {keyword} ({len(rows)})")
        table.add_column("Path", overflow="fold")
        if not only_files:
            table.add_column("Snippet")
        for r in rows:
            if only_files:
                table.add_row(r)
            else:
                if ':' in r:
                    path_part, snippet = r.split(':', 1)
                    table.add_row(path_part, snippet[:120])
                else:
                    table.add_row(r, '')
        console.print(table)
    else:
        for r in rows:
            console.print(r)


@app.command("search")
def search(
    keyword: str = typer.Argument(None, help="关键词 (可通过管道输入覆盖)"),
    path: Path = typer.Option(None, "--path", "-p", help="搜索根路径，缺省尝试剪贴板路径或当前目录"),
    files: bool = typer.Option(True, "--files/--lines", help="仅列出匹配文件 (或列出含行内容)"),
    icase: bool = typer.Option(True, "--icase/--no-icase", help="忽略大小写"),
    table: bool = typer.Option(True, "--table/--no-table", help="表格展示"),
    glob: list[str] = typer.Option(None, "--glob", help="传给 ripgrep 的 -g 通配 (可多次)"),
    exts: str = typer.Option('', "--exts", help="备用 Python 搜索时限制扩展(逗号分隔)"),
    copy: bool = typer.Option(False, "--copy", help="复制结果路径到剪贴板"),
    json_out: Path = typer.Option(None, "--json-out", help="写出 JSON 文件"),
    limit: int = typer.Option(0, "--limit", help="限制展示条数 (0 不限制)"),
    pipe: bool = typer.Option(False, "--pipe", help="强制从标准输入读取多行关键词"),
    keywords_file: Path = typer.Option(None, "--keywords-file", help="从文件读取多行关键词 (优先级最高)")
):
    piped = None
    if keywords_file:
        if not keywords_file.exists():
            raise typer.BadParameter(f"关键词文件不存在: {keywords_file}")
        piped = keywords_file.read_text(encoding='utf-8', errors='ignore')
    else:
        piped = detect_piped_input() if not pipe else sys.stdin.read()
    multi_keywords: list[str] = []
    display_keyword = ''
    if piped:
        # 多行 -> 多关键词 OR
        parts = [p.strip() for p in piped.replace('\r','').split('\n') if p.strip()]
        if len(parts) > 1:
            multi_keywords = parts
        elif parts:
            keyword = parts[0]
    if keyword:
        display_keyword = keyword
    if multi_keywords:
        display_keyword = '|'.join(multi_keywords)
    if not (keyword or multi_keywords):
        raise typer.BadParameter("缺少关键词 (参数或管道)")

    if path is None:
        clip = pyperclip.paste().strip()
        if clip and Path(clip).exists():
            path = Path(clip)
        else:
            path = Path.cwd()

    if not path.exists():
        raise typer.BadParameter(f"路径不存在: {path}")

    # 优先 ripgrep
    lines: list[str]
    rg_available = shutil.which('rg') is not None
    search_exts = [e.strip().lower() for e in exts.split(',') if e.strip()] or DEFAULT_EXTS
    if rg_available:
        if multi_keywords:
            # 组建 | 正则，转义每个关键词
            pattern = '(' + '|'.join(re.escape(k) for k in multi_keywords) + ')'
        else:
            pattern = keyword
        cmd = build_ripgrep_command(pattern, path, files, icase, glob)
        try:
            lines = run_ripgrep(cmd)
        except Exception as e:
            console.print(f"[red]ripgrep 执行失败, fallback Python: {e}[/red]")
            lines = python_fallback_search(multi_keywords or [keyword], path, search_exts, files)
    else:
        lines = python_fallback_search(multi_keywords or [keyword], path, search_exts, files)

    if limit > 0:
        lines = lines[:limit]

    present_results(lines, display_keyword, table, files)

    if copy and lines:
        to_copy = '\n'.join(lines if not files else sorted(set(lines)))
        pyperclip.copy(to_copy)
        console.print('[green]已复制[/green]')

    if json_out:
        json_out.write_text(json.dumps(lines, ensure_ascii=False, indent=2), encoding='utf-8')
        console.print(f'[green]JSON -> {json_out}[/green]')


@app.command('interactive')
def interactive():
    """交互式模式：循环输入关键词搜索 (回车退出)"""
    base = None
    clip = pyperclip.paste().strip()
    if clip and Path(clip).exists():
        base = Path(clip)
    while True:
        kw = Prompt.ask('关键词(回车退出)', default='')
        if not kw:
            break
        search.callback(kw, base or Path.cwd())  # type: ignore


def main_entry():
    piped = detect_piped_input()
    if len(sys.argv) == 1:
        if piped:  # 直接执行一次搜索
            clip = pyperclip.paste().strip()
            root = Path(clip) if clip and Path(clip).exists() else Path.cwd()
            search.callback(piped, root)  # type: ignore
            return
        # 进入交互: 先确定路径
        clip = pyperclip.paste().strip()
        root = Path(clip) if clip and Path(clip).exists() else Path.cwd()
        console.print(Panel(f"[bold cyan]searcha 交互模式[/bold cyan]\n根路径: {root}"))
        while True:
            kw = Prompt.ask('关键词(回车退出)', default='')
            if not kw:
                break
            search.callback(kw, root)  # type: ignore
        return
    app()

if __name__ == '__main__':
    main_entry()
