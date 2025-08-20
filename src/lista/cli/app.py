from __future__ import annotations
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from pathlib import Path
import pyperclip
import json
from ..core.store import ArtistStore
from ..core.service import ArtistService
from ..core.models import ArtistRecord
from datetime import datetime
import os
import json as json_lib

from .interactive import interactive_menu  # 分离的交互菜单

app = typer.Typer(add_completion=False, help="画师信息维护工具 (Typer 交互版)")
console = Console()

# Shared state
class State:
    config: dict | None = None
    store: ArtistStore | None = None
    service: ArtistService | None = None
    base_dir: Path | None = None
    db_path: Path | None = None

state = State()

def load_config(path: Path) -> dict:
    if not path.exists():
        return {
            "paths": {"base_dir": "E:/1EHV"},
            "exclude_keywords": ["汉化","翻译","Chinese","中文","简体","繁体",".zip",".rar",".7z"]
        }
    return json.loads(path.read_text(encoding='utf-8'))

def bootstrap(config: Path | None = None, db: Path | None = None):
    """手动初始化（允许脚本方式或 Typer 回调共用）"""
    if config is None:
        config = Path(__file__).resolve().parent.parent / 'config.json'
    if db is None:
        db = Path(__file__).resolve().parent.parent / 'artists_db.json'
    cfg = load_config(config)
    state.config = cfg
    state.db_path = db
    state.base_dir = Path(cfg.get('paths',{}).get('base_dir','E:/1EHV'))
    state.store = ArtistStore(db)
    state.service = ArtistService(state.store, cfg)

@app.callback()
def init(
    ctx: typer.Context,
    config: Path = typer.Option(Path(__file__).resolve().parent.parent / 'config.json', help='配置文件路径'),
    db: Path = typer.Option(Path(__file__).resolve().parent.parent / 'artists_db.json', help='数据库文件路径'),
):
    bootstrap(config, db)

@app.command('scan')
def scan(
    path: Path = typer.Option(None, help='扫描路径（默认 config base_dir）'),
    category: str = typer.Option('auto', help='分类'),
    clipboard: bool = typer.Option(False, '--clipboard', help='从剪贴板读取路径'),
):
    if clipboard:
        clip = pyperclip.paste().strip()
        if clip:
            path = Path(clip)
            console.print(f"使用剪贴板路径: [bold]{path}[/bold]")
    if path is None:
        path = state.base_dir
    added = state.service.scan_folder(path, category)
    console.print(f"扫描完成: 新增/更新 {added} 条")

@app.command('add')
def add(
    folder: str = typer.Option(..., '--folder', '-f'),
    names: str = typer.Option(..., '--names', '-n', help='逗号或空格分隔'),
    category: str = typer.Option('auto', '--category', '-g')
):
    parts = [p.strip() for p in names.replace('，', ',').replace(',', ' ').split() if p.strip()]
    state.service.add_manual(folder, parts, category)
    console.print(f"添加/更新: {folder} -> {parts} ({category})")

@app.command('set')
def set_category(target: str, category: str):
    n = state.service.set_category(target, category)
    console.print(f"更新分类 {n} 条 -> {category}")

@app.command('list')
def list_category(
    category: str = typer.Option('all', '--category', '-g'),
    format: str = typer.Option('table', '--format', '-F', help='table|names|json'),
    copy: bool = typer.Option(False, '--copy')
):
    rows = state.store.list(category)
    if format == 'json':
        text = json.dumps([r.to_dict() for r in rows], ensure_ascii=False, indent=2)
    elif format == 'names':
        names = []
        for r in rows:
            names.extend(r.names)
        text = '\n'.join(sorted(set(names)))
    else:
        table = Table(title=f"分类: {category}")
        table.add_column('Folder', style='cyan', overflow='fold')
        table.add_column('Category', style='magenta')
        table.add_column('Names', style='green')
        for r in rows:
            table.add_row(r.folder, r.category, ','.join(r.names))
        console.print(table)
        text = None
    if text is not None:
        console.print(text)
    if copy and text is not None:
        pyperclip.copy(text)
        console.print('[bold green]已复制到剪贴板[/bold green]')

@app.command('search')
def search(keyword: str, format: str = typer.Option('table','--format','-F'), copy: bool = typer.Option(False,'--copy')):
    rows = state.store.search(keyword)
    if format == 'json':
        text = json.dumps([r.to_dict() for r in rows], ensure_ascii=False, indent=2)
    elif format == 'names':
        names = []
        for r in rows:
            names.extend(r.names)
        text = '\n'.join(sorted(set(names)))
    else:
        table = Table(title=f"搜索: {keyword} ({len(rows)})")
        table.add_column('Folder', style='cyan', overflow='fold')
        table.add_column('Category', style='magenta')
        table.add_column('Names', style='green')
        for r in rows:
            table.add_row(r.folder, r.category, ','.join(r.names))
        console.print(table)
        text = None
    if text is not None:
        console.print(text)
    if copy and text is not None:
        pyperclip.copy(text)
        console.print('[bold green]已复制到剪贴板[/bold green]')

@app.command('remove')
def remove(target: str):
    n = state.store.remove(target)
    console.print(f"删除 {n} 条")

@app.command('export')
def export(category: str = typer.Option('all','--category','-g'), out: Path = typer.Option(...,'--out','-o')):
    state.store.export(category, out)
    console.print(f"已导出 -> {out}")

@app.command('stats')
def stats():
    rows = state.store.list('all')
    total = len(rows)
    from collections import Counter
    c = Counter(r.category for r in rows)
    lines = [f"总数: {total}"] + [f"{k}: {v}" for k, v in c.most_common()]
    console.print(Panel('\n'.join(lines), title='统计'))

@app.command('output')
def output(
    category: str = typer.Option('all', '--category', '-g', help='分类(用于 list 模式)'),
    keyword: str = typer.Option('', '--keyword', '-k', help='搜索关键字(提供则执行 search)'),
    format: str = typer.Option('names', '--format', '-F', help='table|names|json'),
    out: Path = typer.Option(None, '--out', '-o', help='输出 JSON 文件路径'),
    overwrite: bool = typer.Option(True, '--overwrite/--no-overwrite', help='允许覆盖已存在文件'),
    copy: bool = typer.Option(False, '--copy', help='复制输出文本到剪贴板')
):
    """统一输出: 不再支持管道读取；默认生成固定文件名，方便其它工具读取。

    默认文件命名规则(未指定 --out):
      format == names -> lista_{category或search}_names.txt (纯文本)
      format == json  -> lista_{category或search}_json.json
      format == table -> lista_{category或search}_table.json
    """
    # 获取数据
    if keyword:
        rows = state.store.search(keyword)
        title = f'搜索: {keyword}'
    else:
        rows = state.store.list(category)
        title = f'分类: {category}'

    json_data = [r.to_dict() for r in rows]
    output_text = ''
    if format == 'json':
        output_text = json.dumps(json_data, ensure_ascii=False, indent=2)
        console.print(Panel(output_text, title=title))
    elif format == 'names':
        names = sorted({n for r in rows for n in r.names})
        output_text = '\n'.join(names)
        console.print(output_text)
        json_data = names
    else:  # table
        table = Table(title=f'{title} ({len(rows)})')
        table.add_column('Folder', style='cyan', overflow='fold')
        table.add_column('Category', style='magenta')
        table.add_column('Names', style='green')
        for r in rows:
            table.add_row(r.folder, r.category, ','.join(r.names))
        console.print(table)
        output_text = '\n'.join(sorted({n for r in rows for n in r.names}))

    if copy and output_text:
        pyperclip.copy(output_text)
        console.print('[green]已复制到剪贴板[/green]')

    if out is None:
        base = 'search' if keyword else category
        if format == 'names':
            out = Path(f'lista_{base}_names.txt')
        elif format == 'json':
            out = Path(f'lista_{base}_json.json')
        else:
            out = Path(f'lista_{base}_table.json')
    if out.exists() and not overwrite:
        raise typer.BadParameter(f'文件已存在: {out}')
    if format == 'names':
        out.write_text(output_text, encoding='utf-8')
    else:
        out.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding='utf-8')
    console.print(f'[green]已写出 -> {out}[/green]')

def main_entry():
    """脚本入口: 无参数 -> Rich 菜单交互；有参数 -> Typer CLI"""
    import sys
    if len(sys.argv) == 1:
        bootstrap()
        interactive_menu(state, console)
    else:
        app()

if __name__ == '__main__':  # python -m lista.cli.app
    main_entry()
