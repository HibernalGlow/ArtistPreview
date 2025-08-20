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
        table = Table(title=f"搜索: {keyword}")
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

def _stats_panel():
    rows = state.store.list('all')
    total = len(rows)
    from collections import Counter
    c = Counter(r.category for r in rows)
    lines = [f"总数: {total}"] + [f"{k}: {v}" for k,v in c.most_common()]
    return '\n'.join(lines)

def interactive_menu():
    console.clear()
    console.print(Panel("[bold cyan]Lista 交互模式[/bold cyan]\n请选择操作 (输入编号)"))
    while True:
        console.print(Panel(_stats_panel(), title='统计', expand=False))
        console.print("[bold yellow]1[/bold yellow]. 扫描(剪贴板路径) 添加/更新 -> 指定分类\n"
                      "[bold yellow]2[/bold yellow]. 扫描(手动输入路径)\n"
                      "[bold yellow]3[/bold yellow]. 查看分类列表\n"
                      "[bold yellow]4[/bold yellow]. 搜索\n"
                      "[bold yellow]5[/bold yellow]. 添加手动条目\n"
                      "[bold yellow]6[/bold yellow]. 修改分类\n"
                      "[bold yellow]7[/bold yellow]. 删除条目\n"
                      "[bold yellow]8[/bold yellow]. 导出分类\n"
                      "[bold yellow]9[/bold yellow]. 刷新统计\n"
                      "[bold yellow]0[/bold yellow]. 退出")
        choice = Prompt.ask("选择", choices=[str(i) for i in range(0,10)], default='9')
        try:
            if choice == '0':
                break
            elif choice == '1':
                cat = Prompt.ask('分类', default='auto')
                clip = pyperclip.paste().strip()
                path = Path(clip)
                if not path.exists():
                    console.print('[red]剪贴板路径不存在[/red]')
                else:
                    added = state.service.scan_folder(path, cat)
                    console.print(f'[green]完成: {added} 条[/green]')
            elif choice == '2':
                p = Prompt.ask('输入路径', default=str(state.base_dir))
                cat = Prompt.ask('分类', default='auto')
                added = state.service.scan_folder(Path(p), cat)
                console.print(f'[green]完成: {added} 条[/green]')
            elif choice == '3':
                cat = Prompt.ask('分类(all/auto/white/black/自定义)', default='all')
                fmt = Prompt.ask('格式(table/names/json)', choices=['table','names','json'], default='table')
                rows = state.store.list(cat)
                if fmt == 'table':
                    table = Table(title=f'分类: {cat}')
                    table.add_column('Folder'); table.add_column('Category'); table.add_column('Names')
                    for r in rows:
                        table.add_row(r.folder, r.category, ','.join(r.names))
                    console.print(table)
                elif fmt == 'names':
                    names = sorted({n for r in rows for n in r.names})
                    console.print('\n'.join(names))
                else:
                    console.print(json.dumps([r.to_dict() for r in rows], ensure_ascii=False, indent=2))
                if Confirm.ask('复制到剪贴板?', default=False):
                    if fmt == 'table':
                        # fallback names copy
                        names = sorted({n for r in rows for n in r.names})
                        pyperclip.copy('\n'.join(names))
                    else:
                        # need text variable reuse
                        pass
                    console.print('[green]已复制[/green]')
            elif choice == '4':
                kw = Prompt.ask('关键字')
                rows = state.store.search(kw)
                table = Table(title=f'搜索: {kw} ({len(rows)})')
                table.add_column('Folder'); table.add_column('Category'); table.add_column('Names')
                for r in rows:
                    table.add_row(r.folder, r.category, ','.join(r.names))
                console.print(table)
            elif choice == '5':
                folder = Prompt.ask('Folder(含中括号)')
                cat = Prompt.ask('分类', default='auto')
                names_raw = Prompt.ask('名称(逗号/空格分隔)')
                parts = [p.strip() for p in names_raw.replace('，',',').replace(',', ' ').split() if p.strip()]
                state.service.add_manual(folder, parts, cat)
                console.print('[green]OK[/green]')
            elif choice == '6':
                target = Prompt.ask('名称或Folder')
                cat = Prompt.ask('新分类')
                n = state.service.set_category(target, cat)
                console.print(f'[green]更新 {n} 条[/green]')
            elif choice == '7':
                target = Prompt.ask('名称或Folder')
                if Confirm.ask('确认删除?', default=False):
                    n = state.store.remove(target)
                    console.print(f'[red]删除 {n} 条[/red]')
            elif choice == '8':
                cat = Prompt.ask('分类(导出)', default='all')
                out = Prompt.ask('输出文件名', default=f'export_{cat}.json')
                state.store.export(cat, Path(out))
                console.print('[green]已导出[/green]')
            elif choice == '9':
                # refresh just continues
                pass
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f'[red]错误: {e}[/red]')

@app.command('stats')
def stats():
    console.print(Panel(_stats_panel(), title='统计'))

def main_entry():
    """脚本入口: 无参数 -> Rich 菜单交互；有参数 -> Typer CLI"""
    import sys
    if len(sys.argv) == 1:
        bootstrap()
        interactive_menu()
    else:
        app()

if __name__ == '__main__':  # python -m lista.cli.app
    main_entry()
