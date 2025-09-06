"""
seriex 命令行接口 - 使用Typer实现
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
from rich.tree import Tree

from .extractor import seriex

# 创建Typer应用
app = typer.Typer(
    help="漫画压缩包系列提取工具",
    add_completion=False,
)

# 创建Rich控制台
console = Console()


@app.command()
def extract(
    paths: List[str] = typer.Argument(None, help="要处理的路径列表"),
    clipboard: bool = typer.Option(False, "--clipboard", "-c", help="从剪贴板读取路径"),
    config: Optional[str] = typer.Option(None, "--config", "-C", help="TOML 配置文件路径（可指定支持的格式，默认含 mp4/nov/zip 与常见压缩包）"),
    prefix: Optional[str] = typer.Option(None, "--prefix", help="自定义系列前缀（覆盖配置）"),
    add_prefix: Optional[bool] = typer.Option(None, "--add-prefix/--no-add-prefix", help="是否为新建系列文件夹添加前缀（可覆盖配置）"),
    similarity: float = typer.Option(75.0, help="设置基本相似度阈值(0-100)，默认75"),
    ratio: float = typer.Option(75.0, help="设置完全匹配阈值(0-100)，默认75"),
    partial: float = typer.Option(85.0, help="设置部分匹配阈值(0-100)，默认85"),
    token: float = typer.Option(80.0, help="设置标记匹配阈值(0-100)，默认80"),
    length_diff: float = typer.Option(0.3, help="设置长度差异最大值(0-1)，默认0.3"),
):
    """执行漫画压缩包系列提取操作"""
    
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

    # 设置相似度配置
    similarity_config = {
        'THRESHOLD': similarity,
        'RATIO_THRESHOLD': ratio,
        'PARTIAL_THRESHOLD': partial,
        'TOKEN_THRESHOLD': token,
        'LENGTH_DIFF_MAX': length_diff
    }
    
    # 创建提取器
    extractor = seriex(similarity_config, config_path=config, add_prefix=add_prefix)
    # 覆盖前缀（运行时）
    if prefix is not None:
        extractor.config["prefix"] = prefix
    
    # 处理每个路径
    success_count = 0
    for path in all_paths:
        path = path.strip('"').strip("'")
        if os.path.exists(path):
            if os.path.isdir(path):
                typer.echo(f"\n📂 处理目录: {path}")
                # 先做预处理(plan)
                plan = extractor.prepare_directory(path)
                if plan:
                    tree = Tree(f"计划: {path}")
                    for d, groups in plan.items():
                        dnode = tree.add(d)
                        for folder, files in groups.items():
                            fnode = dnode.add(f"{folder}")
                            for fp in files:
                                fnode.add(os.path.basename(fp))
                    console.print(tree)
                    if not Confirm.ask("是否执行上述计划?", default=True):
                        continue
                # 执行
                summary = extractor.apply_prepared_plan(path)
                if summary:
                    success_count += 1
                    # 输出汇总树
                    tree = Tree(f"结果: {path}")
                    for d, groups in summary.items():
                        dnode = tree.add(d)
                        for folder, files in groups.items():
                            fnode = dnode.add(f"{folder}")
                            for fn in files:
                                fnode.add(fn)
                    console.print(tree)
            else:
                typer.echo(f"⚠️ 跳过文件 {path}，只能处理目录")
@app.command()
def plan(
    paths: List[str] = typer.Argument(None, help="要预处理的路径列表"),
    clipboard: bool = typer.Option(False, "--clipboard", "-c", help="从剪贴板读取路径"),
    config: Optional[str] = typer.Option(None, "--config", "-C", help="TOML 配置文件路径"),
    prefix: Optional[str] = typer.Option(None, "--prefix", help="自定义系列前缀（覆盖配置）"),
    add_prefix: Optional[bool] = typer.Option(None, "--add-prefix/--no-add-prefix", help="是否为新建系列文件夹添加前缀（可覆盖配置）"),
):
    """仅预处理，展示移动计划，不执行。"""
    all_paths = list(paths) if paths else []
    if clipboard:
        try:
            import pyperclip
            clipboard_content = pyperclip.paste().strip()
            if clipboard_content:
                all_paths.extend([p.strip() for p in clipboard_content.replace('\r\n','\n').split('\n') if p.strip()])
        except ImportError:
            typer.echo("未安装 pyperclip，无法从剪贴板读取。")

    if not all_paths:
        all_paths.append(os.getcwd())

    extractor = seriex(config_path=config, add_prefix=add_prefix)
    if prefix is not None:
        extractor.config["prefix"] = prefix

    for path in all_paths:
        path = path.strip('"').strip("'")
        if not os.path.isdir(path):
            typer.echo(f"❌ 路径不是目录: {path}")
            continue
        plan = extractor.prepare_directory(path)
        tree = Tree(f"计划: {path}")
        if plan:
            for d, groups in plan.items():
                dnode = tree.add(d)
                for folder, files in groups.items():
                    fnode = dnode.add(f"{folder}")
                    for fp in files:
                        fnode.add(os.path.basename(fp))
        else:
            tree.add("无可执行计划")
        console.print(tree)
        # typer.echo(f"❌ 路径不存在: {path}")

def interactive():
    """使用Rich库实现的交互式界面"""
    
    # 显示欢迎信息
    console.print(Panel.fit(
        "[bold yellow]漫画压缩包系列提取工具[/bold yellow]\n"
        "[cyan]该工具可以自动识别并整理同一系列的漫画压缩包[/cyan]", 
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
    
    # 设置相似度参数
    console.print("\n[bold green]相似度参数配置[/bold green]")
    console.print("[dim]（使用默认值可按回车直接跳过）[/dim]")
    
    threshold = float(Prompt.ask("基本相似度阈值(0-100)", default="75"))
    ratio = float(Prompt.ask("完全匹配阈值(0-100)", default="75"))
    partial = float(Prompt.ask("部分匹配阈值(0-100)", default="85"))
    token = float(Prompt.ask("标记匹配阈值(0-100)", default="80"))
    length_diff = float(Prompt.ask("长度差异最大值(0-1)", default="0.3"))
    
    # 配置相似度
    similarity_config = {
        'THRESHOLD': threshold,
        'RATIO_THRESHOLD': ratio,
        'PARTIAL_THRESHOLD': partial,
        'TOKEN_THRESHOLD': token,
        'LENGTH_DIFF_MAX': length_diff
    }
    
    # 读取可选的 TOML 配置路径
    cfg_path = None
    if Confirm.ask("是否指定 TOML 配置文件?", default=False):
        p = Prompt.ask("请输入 TOML 配置文件路径(留空跳过)").strip()
        if p:
            cfg_path = p
    # 是否添加前缀
    add_prefix = None
    if Confirm.ask("是否为系列文件夹添加前缀?", default=True):
        add_prefix = True
    else:
        add_prefix = False
    # 可选自定义前缀
    custom_prefix = None
    if add_prefix and Confirm.ask("是否自定义前缀?", default=False):
        custom_prefix = Prompt.ask("请输入前缀（如 [#s]）", default="[#s]")
    
    # 创建提取器
    extractor = seriex(similarity_config, config_path=cfg_path, add_prefix=add_prefix)
    if custom_prefix is not None:
        extractor.config["prefix"] = custom_prefix
    
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
                    # 预处理计划
                    plan = extractor.prepare_directory(path)
                    plan_tree = Tree(f"计划: {path}")
                    if plan:
                        for d, groups in plan.items():
                            dnode = plan_tree.add(d)
                            for folder, files in groups.items():
                                fnode = dnode.add(f"{folder}")
                                for fp in files:
                                    fnode.add(os.path.basename(fp))
                    else:
                        plan_tree.add("无可执行计划")
                    console.print(plan_tree)

                    # 确认是否执行
                    if not Confirm.ask("是否执行上述计划?", default=True):
                        console.print("[yellow]已跳过执行[/yellow]")
                    else:
                        summary = extractor.apply_prepared_plan(path)
                        if summary:
                            success_count += 1
                            console.print(f"[green]✓ 成功处理目录: {path}[/green]")
                            # 输出结果树
                            res_tree = Tree(f"结果: {path}")
                            for d, groups in summary.items():
                                dnode = res_tree.add(d)
                                for folder, files in groups.items():
                                    fnode = dnode.add(f"{folder}")
                                    for fn in files:
                                        fnode.add(fn)
                            console.print(res_tree)
                        else:
                            console.print(f"[yellow]⚠ 无变更或执行失败: {path}[/yellow]")
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
    """seriex 主函数"""
    # 如果没有子命令被调用，则启动交互模式
    if ctx.invoked_subcommand is None:
        interactive()


if __name__ == "__main__":
    app()