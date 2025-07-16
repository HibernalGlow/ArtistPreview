import os
import difflib
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table

console = Console()

def get_similarity(s1, s2):
    """计算两个字符串的相似度"""
    return difflib.SequenceMatcher(None, s1, s2).ratio()

def get_multiline_input(prompt_message):
    """获取多行输入，空行结束"""
    console.print(f"[yellow]{prompt_message}[/yellow] (输入空行结束)")
    lines = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line.strip())
    return lines

def main():
    console.print(Panel("[bold cyan]文件夹相似度检测与批量移动工具[/bold cyan]", border_style="green"))
    
    # 用户输入目标文件夹名称列表
    console.print("[yellow]请输入多个目标文件夹名称[/yellow] (每行一个，输入空行结束)")
    target_folder_names = get_multiline_input("请输入多个目标文件夹名称")
    
    # 显示用户输入的目标文件夹名称
    table = Table(title="目标文件夹名称")
    table.add_column("序号", justify="center", style="cyan")
    table.add_column("文件夹名称", style="green")
    
    for i, name in enumerate(target_folder_names, 1):
        table.add_row(str(i), name)
    
    console.print(table)
    
    # 用户输入源文件夹路径
    console.print("[yellow]请输入多个源文件夹路径[/yellow] (每行一个，输入空行结束，默认为E:\\1EHV)")
    source_paths = get_multiline_input("请输入多个源文件夹路径")
    if not source_paths:
        source_paths = ["E:\\1EHV"]
    
    # 用户输入目标文件夹路径
    destination_path = Prompt.ask("[yellow]请输入目标文件夹路径[/yellow] (默认为E:\\2EHV\\crash)", default="E:\\2EHV\\crash")
    
    # 用户输入相似度阈值
    similarity_threshold = float(Prompt.ask("[yellow]请输入相似度阈值[/yellow] (0-1之间，默认0.8)", default="0.8"))
    
    # 创建目标文件夹（如果不存在）
    os.makedirs(destination_path, exist_ok=True)
    
    similar_folders = []
    
    # 检测源文件夹中的相似文件夹
    with Progress() as progress:
        task = progress.add_task("[cyan]扫描文件夹...", total=len(source_paths))
        
        for source_path in source_paths:
            progress.update(task, advance=1, description=f"[cyan]扫描 {source_path}...")
            try:
                # 获取源文件夹下的一级子文件夹
                subfolders = [f for f in os.listdir(source_path) if os.path.isdir(os.path.join(source_path, f))]
                
                for subfolder in subfolders:
                    for target_name in target_folder_names:
                        similarity = get_similarity(subfolder.lower(), target_name.lower())
                        if similarity >= similarity_threshold:
                            similar_folders.append({
                                "name": subfolder,
                                "path": os.path.join(source_path, subfolder),
                                "target": target_name,
                                "similarity": similarity
                            })
            except Exception as e:
                console.print(f"[bold red]扫描 {source_path} 时出错: {str(e)}[/bold red]")
    
    # 显示找到的相似文件夹
    if similar_folders:
        table = Table(title="找到的相似文件夹")
        table.add_column("序号", justify="center", style="cyan")
        table.add_column("文件夹名称", style="green")
        table.add_column("文件夹路径", style="blue")
        table.add_column("目标匹配", style="magenta")
        table.add_column("相似度", justify="right", style="yellow")
        
        for i, folder in enumerate(similar_folders, 1):
            table.add_row(
                str(i),
                folder["name"],
                folder["path"],
                folder["target"],
                f"{folder['similarity']:.2f}"
            )
        
        console.print(table)
        
        # 选择输出格式
        console.print("\n[bold cyan]输出选项：[/bold cyan]")
        console.print("[cyan]1. 输出原文件夹路径[/cyan]")
        console.print("[cyan]2. 输出目标文件夹路径[/cyan]")
        
        output_choice = Prompt.ask(
            "[bold yellow]选择输出格式[/bold yellow]",
            choices=["1", "2"],
            default="1"
        )
        
        console.print("\n[bold green]重复文件夹路径列表：[/bold green]")
        
        for i, folder in enumerate(similar_folders, 1):
            if output_choice == "1":
                # 输出原文件夹路径，关闭markup避免路径中的特殊字符被转义
                console.print(f"{i}. ", end="")
                console.print(folder["path"], markup=False)
            else:
                # 输出目标文件夹路径
                target_subfolder = os.path.join(destination_path, folder["target"])
                destination = os.path.join(target_subfolder, folder["name"])
                console.print(f"{i}. ", end="")
                console.print(destination, markup=False)
    else:
        console.print("[yellow]未找到符合条件的相似文件夹[/yellow]")

if __name__ == "__main__":
    main()