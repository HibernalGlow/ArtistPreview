from __future__ import annotations
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
import pyperclip
import json


def _stats_text(store) -> str:
    rows = store.list('all')
    total = len(rows)
    from collections import Counter
    c = Counter(r.category for r in rows)
    lines = [f"总数: {total}"] + [f"{k}: {v}" for k, v in c.most_common()]
    return '\n'.join(lines)


def interactive_menu(state, console: Console):
    """Rich 交互菜单。传入 state 与 console，避免循环依赖。"""
    console.clear()
    console.print(Panel("[bold cyan]Lista 交互模式[/bold cyan]\n请选择操作 (输入编号)"))
    while True:
        console.print(Panel(_stats_text(state.store), title='统计', expand=False))
        console.print(
            "[bold yellow]1[/bold yellow]. 扫描(剪贴板路径) 添加/更新 -> 指定分类\n"
            "[bold yellow]2[/bold yellow]. 扫描(手动输入路径)\n"
            "[bold yellow]3[/bold yellow]. 查看分类列表\n"
            "[bold yellow]4[/bold yellow]. 搜索\n"
            "[bold yellow]5[/bold yellow]. 添加手动条目\n"
            "[bold yellow]6[/bold yellow]. 修改分类\n"
            "[bold yellow]7[/bold yellow]. 删除条目\n"
            "[bold yellow]8[/bold yellow]. 导出分类\n"
            "[bold yellow]9[/bold yellow]. 刷新统计\n"
            "[bold yellow]0[/bold yellow]. 退出"
        )
        choice = Prompt.ask("选择", choices=[str(i) for i in range(0, 10)], default='9')
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
                fmt = Prompt.ask('格式(table/names/json)', choices=['table', 'names', 'json'], default='table')
                rows = state.store.list(cat)
                copied_text = ''
                if fmt == 'table':
                    table = Table(title=f'分类: {cat}')
                    table.add_column('Folder')
                    table.add_column('Category')
                    table.add_column('Names')
                    for r in rows:
                        table.add_row(r.folder, r.category, ','.join(r.names))
                    console.print(table)
                    # 默认复制 names 列
                    copied_text = '\n'.join(sorted({n for r in rows for n in r.names}))
                elif fmt == 'names':
                    names = sorted({n for r in rows for n in r.names})
                    text = '\n'.join(names)
                    console.print(text)
                    copied_text = text
                else:  # json
                    text = json.dumps([r.to_dict() for r in rows], ensure_ascii=False, indent=2)
                    console.print(text)
                    copied_text = text
                if Confirm.ask('复制到剪贴板?', default=False):
                    pyperclip.copy(copied_text)
                    console.print('[green]已复制[/green]')
            elif choice == '4':
                kw = Prompt.ask('关键字')
                rows = state.store.search(kw)
                table = Table(title=f'搜索: {kw} ({len(rows)})')
                table.add_column('Folder')
                table.add_column('Category')
                table.add_column('Names')
                for r in rows:
                    table.add_row(r.folder, r.category, ','.join(r.names))
                console.print(table)
            elif choice == '5':
                folder = Prompt.ask('Folder(含中括号)')
                cat = Prompt.ask('分类', default='auto')
                names_raw = Prompt.ask('名称(逗号/空格分隔)')
                parts = [p.strip() for p in names_raw.replace('，', ',').replace(',', ' ').split() if p.strip()]
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
                # refresh
                pass
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f'[red]错误: {e}[/red]')
