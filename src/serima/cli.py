"""
serima 命令行接口 - 使用Typer实现
"""

import os
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .classifier import MangaClassifier

# 创建Typer应用
app = typer.Typer(
    help="漫画压缩包分类整理工具",
    add_completion=False,
)

# 创建Rich控制台
console = Console()


@app.command()
def classify(
    paths: Optional[List[str]] = typer.Argument([], help="要处理的路径列表"),
    clipboard: bool = typer.Option(False, "--clipboard", "-c", help="从剪贴板读取路径"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="递归处理子目录"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="指定输出目录（如果不指定则使用输入目录）"),
    category: Optional[List[str]] = typer.Option(None, help="自定义分类文件夹，格式为\"显示名称:关键词1,关键词2\""),
    threads: int = typer.Option(16, help="最大工作线程数，默认16"),
):
    """执行漫画压缩包分类操作"""
    
    # 收集路径
    all_paths = list(paths) if paths else []
    
    # 从剪贴板获取路径
    if clipboard:
        try:
            import pyperclip
            clipboard_content = pyperclip.paste().strip()
            if clipboard_content:
                clipboard_paths = [p.strip() for p in clipboard_content.replace('\r\n', '\n').split('\n') if p.strip()]
                all_paths.extend(clipboard_paths)
                typer.echo("从剪贴板读取到以下路径：")
                for path in clipboard_paths:
                    typer.echo(f"  - {path}")
        except ImportError:
            typer.echo("未安装 pyperclip 模块，无法从剪贴板读取路径。请通过 pip install pyperclip 安装。")
    
    # 如果没有提供路径，使用当前目录
    if not all_paths:
        all_paths.append(os.getcwd())
        typer.echo(f"没有提供路径，使用当前目录: {all_paths[0]}")
    
    # 创建分类器
    classifier = MangaClassifier(
        category_folders=category,
        max_workers=threads
    )
    
    # 处理每个路径
    success_count = 0
    for path in all_paths:
        path = path.strip('"').strip("'")
        if os.path.exists(path):
            if os.path.isdir(path):
                typer.echo(f"\n📂 处理目录: {path}")
                try:
                    output_dir = output if output else path
                    # 确认输出目录
                    if output:
                        typer.echo(f"输出目录: {output_dir}")
                    
                    # 处理目录
                    stats = classifier.process_directory(
                        path,
                        output_dir=output_dir,
                        recursive=recursive
                    )
                    
                    if stats["processed"] > 0:
                        success_count += 1
                except Exception as e:
                    typer.echo(f"处理目录时出错: {str(e)}")
            else:
                typer.echo(f"⚠️ 跳过文件 {path}，只能处理目录")
        else:
            typer.echo(f"❌ 路径不存在: {path}")
    
    # 显示处理结果
    if success_count > 0:
        typer.echo(f"\n✅ 成功处理了 {success_count}/{len(all_paths)} 个路径")
    else:
        typer.echo("\n❌ 没有成功处理任何路径")

def interactive():
    """使用Rich库实现的交互式界面"""
    
    # 显示欢迎信息
    console.print(Panel.fit(
        "[bold yellow]漫画压缩包分类整理工具[/bold yellow]\n"
        "[cyan]该工具可以自动识别并分类整理漫画压缩包[/cyan]", 
        border_style="green"
    ))
    
    # 从用户获取路径
    paths = []
    
    # 询问是否从剪贴板获取路径
    use_clipboard = Confirm.ask("是否从剪贴板读取路径?", default=True)
    if use_clipboard:
        try:
            import pyperclip
            clipboard_content = pyperclip.paste().strip()
            if clipboard_content:
                clipboard_paths = [p.strip() for p in clipboard_content.replace('\r\n', '\n').split('\n') if p.strip()]
                
                # 显示从剪贴板读取的路径
                if clipboard_paths:
                    table = Table(title="从剪贴板读取的路径")
                    table.add_column("路径", style="cyan")
                    for path in clipboard_paths:
                        table.add_row(path)
                    console.print(table)
                    
                    if Confirm.ask("确认使用这些路径?", default=True):
                        paths.extend(clipboard_paths)
                else:
                    console.print("[yellow]剪贴板中没有发现有效路径[/yellow]")
        except ImportError:
            console.print("[red]未安装 pyperclip 模块，无法从剪贴板读取路径。请通过 pip install pyperclip 安装。[/red]")
    
    # 询问是否手动添加路径
    if Confirm.ask("是否需要手动添加路径?", default=bool(not paths)):
        while True:
            path = Prompt.ask("请输入路径(留空以结束输入)")
            if not path:
                break
            paths.append(path)
    
    # 如果没有提供路径，使用当前目录
    if not paths:
        current_dir = os.getcwd()
        console.print(f"[yellow]没有提供路径，将使用当前目录:[/yellow] [cyan]{current_dir}[/cyan]")
        paths.append(current_dir)

    # 询问其他选项
    recursive = Confirm.ask("是否递归处理子目录?", default=False)
    
    output = None
    if Confirm.ask("是否指定输出目录?", default=False):
        output = Prompt.ask("请输入输出目录路径")
    
    # 询问自定义分类
    categories = []
    if Confirm.ask("是否添加自定义分类?", default=False):
        console.print("[cyan]请按照格式输入自定义分类：[/cyan] [dim]显示名称:关键词1,关键词2[/dim]")
        while True:
            category = Prompt.ask("自定义分类(留空以结束输入)")
            if not category:
                break
            categories.append(category)
    
    # 询问线程数
    threads = int(Prompt.ask("最大工作线程数", default="16"))
    
    # 创建分类器
    classifier = MangaClassifier(
        category_folders=categories,
        max_workers=threads
    )
    
    # 处理路径
    success_count = 0
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]处理路径...[/cyan]", total=len(paths))
        
        for path in paths:
            path = path.strip('"').strip("'")
            progress.update(task, description=f"[cyan]处理: {path}[/cyan]")
            
            if os.path.exists(path):
                if os.path.isdir(path):
                    console.print(f"\n[bold green]📂 处理目录:[/bold green] {path}")
                    try:
                        output_dir = output if output else path
                        # 确认输出目录
                        if output:
                            console.print(f"[blue]输出目录:[/blue] {output_dir}")
                        
                        # 处理目录
                        stats = classifier.process_directory(
                            path,
                            output_dir=output_dir,
                            recursive=recursive
                        )
                        
                        if stats["processed"] > 0:
                            success_count += 1
                            console.print(f"[green]✓ 成功处理目录: {path}[/green]")
                        else:
                            console.print(f"[yellow]⚠ 没有处理任何文件: {path}[/yellow]")
                    except Exception as e:
                        console.print(f"[red]❌ 处理目录时出错: {str(e)}[/red]")
                else:
                    console.print(f"[yellow]⚠ 跳过文件 {path}，只能处理目录[/yellow]")
            else:
                console.print(f"[red]❌ 路径不存在: {path}[/red]")
            
            progress.update(task, advance=1)
    
    # 显示处理结果
    if success_count > 0:
        console.print(f"\n[bold green]✅ 成功处理了 {success_count}/{len(paths)} 个路径[/bold green]")
    else:
        console.print("\n[bold red]❌ 没有成功处理任何路径[/bold red]")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """serima 主函数"""
    # 如果没有子命令被调用，则启动交互模式
    if ctx.invoked_subcommand is None:
        interactive()


if __name__ == "__main__":
    app()