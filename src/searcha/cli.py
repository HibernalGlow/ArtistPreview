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

app = typer.Typer(add_completion=False, help="简化搜索工具：支持黑名单文件 / -c 剪贴板路径 / 可选文件名匹配")
console = Console()

DEFAULT_EXTS = [".jpg", ".png", ".jpeg", ".gif", ".webp", ".zip", ".rar", ".7z"]


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


DEFAULT_KEYWORDS_FILENAME = "lista_black_names.txt"
DEFAULT_LISTFILE_NAME = "list.txt"

@app.command("search")
def search(
    keyword: str = typer.Argument(None, help="单一关键词(可留空: 自动用黑名单文件)"),
    path: Path = typer.Option(None, "--path", "-p", help="搜索根路径(缺省尝试剪贴板->当前目录)"),
    clip: bool = typer.Option(False, "--clip", "-c", help="强制使用剪贴板路径作为根"),
    include_name: bool = typer.Option(True, "--include-name/--no-include-name", help="按文件名子串匹配"),
    content: bool = typer.Option(False, "--content/--no-content", help="是否扫描文本/小文件内容 (默认不扫描, 仅文件名)"),
    copy: bool = typer.Option(False, "--copy", help="复制结果绝对路径列表到剪贴板"),
    archives_only: bool = typer.Option(True, "--archives-only/--all-files", help="默认只匹配压缩包(.zip/.rar/.7z); 关闭以匹配所有文件"),
    names_file: Path = typer.Option(None, "--names-file", "-n", help="指定包含文件名列表的文本文件 (每行一个文件名)"),
    listfile: Path = typer.Option(None, "--listfile", "-l", help="指定包含完整文件路径列表的文本文件 (每行一个文件路径, 默认 list.txt)"),
):
    # 关键词集合: keyword + 指定文件或默认黑名单文件
    keywords: list[str] = []
    if keyword:
        keywords.append(keyword.strip())
    
    # 优先使用指定的文件名列表文件，否则使用默认黑名单文件
    kw_file = names_file if names_file else Path.cwd() / DEFAULT_KEYWORDS_FILENAME
    if kw_file.exists():
        lines = [l.strip() for l in kw_file.read_text(encoding='utf-8', errors='ignore').splitlines() if l.strip()]
        for l in lines:
            if l not in keywords:
                keywords.append(l)
    elif not names_file:  # 只有当没有指定 names_file 时，才检查默认文件缺失
        pass  # 如果指定了 names_file 但不存在，会在后面报错
    
    if not keywords:
        file_desc = f"{names_file}" if names_file else DEFAULT_KEYWORDS_FILENAME
        raise typer.BadParameter(f"没有可用关键词 (参数为空且缺少 {file_desc})")

    # 路径确定
    if clip:
        clip_path = pyperclip.paste().strip()
        if clip_path and Path(clip_path).exists():
            path = Path(clip_path)
        else:
            raise typer.BadParameter("剪贴板路径无效")
    if path is None:
        clip_path = pyperclip.paste().strip()
        if clip_path and Path(clip_path).exists():
            path = Path(clip_path)
        else:
            path = Path.cwd()
    if not path.exists():
        raise typer.BadParameter(f"路径不存在: {path}")

    # 获取要搜索的文件列表或文件名列表
    file_items: list[str] = []  # 存储路径或文件名字符串
    use_listfile_mode = False
    
    # 如果指定了 listfile 或存在默认的 list.txt，从文件中读取路径/文件名列表
    list_file_to_use = listfile if listfile else (Path.cwd() / DEFAULT_LISTFILE_NAME)
    if listfile or list_file_to_use.exists():
        if not list_file_to_use.exists():
            raise typer.BadParameter(f"文件列表不存在: {list_file_to_use}")
        
        use_listfile_mode = True
        try:
            lines = list_file_to_use.read_text(encoding='utf-8', errors='ignore').splitlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # 移除可能的引号
                line = line.strip('"').strip("'")
                file_items.append(line)
        except Exception as e:
            raise typer.BadParameter(f"读取文件列表失败: {e}")
        
        if not file_items:
            console.print("[yellow]警告: 文件列表为空[/yellow]")
            return

    # 直接文件名匹配; 可选内容匹配(需 --content)
    lowered = [k.lower() for k in keywords]
    results: list[str] = []
    archive_exts = {'.zip', '.rar', '.7z'}
    
    if use_listfile_mode:
        # listfile 模式：直接对文件名/路径字符串进行匹配
        for item in file_items:
            try:
                # 提取文件名部分（可能是完整路径或单独文件名）
                item_lower = item.lower()
                # 获取文件名（如果是路径则取最后一部分）
                filename = Path(item).name.lower()
                
                # 检查扩展名过滤
                suffix = Path(item).suffix.lower()
                if archives_only and suffix not in archive_exts:
                    # 非归档文件：仅当需要内容扫描且开启 content 时才考虑
                    if not (content and (suffix in {'.txt', '.md', '.json'})):
                        continue
                
                # 文件名匹配
                if include_name:
                    if any(k in filename for k in lowered):
                        results.append(item)
                        continue
                
                # 内容匹配（仅当文件实际存在时）
                if content:
                    item_path = Path(item)
                    if item_path.exists() and item_path.is_file():
                        if item_path.suffix.lower() in {'.txt', '.md', '.json'} or item_path.stat().st_size < 512 * 1024:
                            try:
                                with item_path.open('r', encoding='utf-8', errors='ignore') as fh:
                                    for line in fh:
                                        llow = line.lower()
                                        if any(k in llow for k in lowered):
                                            results.append(item)
                                            break
                            except Exception:
                                pass
            except Exception:
                continue
    else:
        # 传统 rglob 模式
        for p in path.rglob('*'):
            try:
                if not p.is_file():
                    continue
                suffix = p.suffix.lower()
                if archives_only and suffix not in archive_exts:
                    # 非归档文件：仅当需要内容扫描且开启 content 时才考虑 (例如某些文本 json)
                    if not (content and (suffix in {'.txt', '.md', '.json'})):
                        continue
                name_l = p.name.lower()
                name_hit = include_name and any(k in name_l for k in lowered)
                if name_hit:
                    results.append(str(p))
                    continue
                if content and (p.suffix.lower() in {'.txt', '.md', '.json'} or p.stat().st_size < 512 * 1024):
                    try:
                        with p.open('r', encoding='utf-8', errors='ignore') as fh:
                            for line in fh:
                                llow = line.lower()
                                if any(k in llow for k in lowered):
                                    results.append(str(p))
                                    break
                    except Exception:
                        pass
            except Exception:
                continue

    # 去重 & 输出
    dedup = []
    seen = set()
    for r in results:
        if r not in seen:
            dedup.append(r); seen.add(r)
    for r in dedup:
        console.print(f'"{r}"')
    console.print(f"[bold cyan]共 {len(dedup)} 条[/bold cyan]")
    if copy and dedup:
        try:
            pyperclip.copy("\n".join(dedup))
            console.print("[green]已复制到剪贴板[/green]")
        except Exception as e:
            console.print(f"[red]复制失败: {e}[/red]")


@app.command('interactive')
def interactive():
    """极简交互: 回车退出, :c 刷新根路径"""
    base = None
    clip_text = pyperclip.paste().strip()
    if clip_text and Path(clip_text).exists():
        base = Path(clip_text)
    while True:
        kw = Prompt.ask('关键词(:c刷新路径, 回车退出)', default='')
        if not kw:
            break
        if kw == ':c':
            clip_new = pyperclip.paste().strip()
            if clip_new and Path(clip_new).exists():
                base = Path(clip_new)
                console.print(f'[cyan]根路径 -> {base}[/cyan]')
            else:
                console.print('[red]无效剪贴板路径[/red]')
            continue
    search(kw, base or Path.cwd())


def main_entry():
    piped = detect_piped_input()
    # 无参数 -> 交互 / 管道单次
    if len(sys.argv) == 1:
        if piped:
            clip = pyperclip.paste().strip()
            root = Path(clip) if clip and Path(clip).exists() else Path.cwd()
            # 直接使用管道内容作为关键词，保持文件黑名单追加逻辑
            search(piped, root)
            return
        interactive()
        return
    # 有参数 -> 正常 Typer 解析
    app()

if __name__ == '__main__':
    main_entry()
