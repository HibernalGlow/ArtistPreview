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

    # 新增：询问是否自动获取目标文件夹
    auto_get = Confirm.ask("是否自动获取目标文件夹（从指定目录下的一级子目录）？", default=False)
    if auto_get:
        auto_dir = Prompt.ask("请输入用于自动获取目标文件夹的目录", default="E:\\1EHV")
        try:
            target_folder_names = []
            target_folder_fullpaths = []
            for f in os.listdir(auto_dir):
                full_path = os.path.join(auto_dir, f)
                if os.path.isdir(full_path):
                    target_folder_names.append(f)
                    target_folder_fullpaths.append(full_path)
            if not target_folder_names:
                console.print(f"[red]目录 {auto_dir} 下未找到子文件夹！[/red]")
                return
        except Exception as e:
            console.print(f"[red]自动获取目标文件夹失败: {str(e)}[/red]")
            return
        # 显示自动获取的目标文件夹
        table = Table(title="自动获取的目标文件夹")
        table.add_column("序号", justify="center", style="cyan")
        table.add_column("文件夹名称", style="green")
        table.add_column("完整路径", style="blue")
        for i, (name, fullpath) in enumerate(zip(target_folder_names, target_folder_fullpaths), 1):
            table.add_row(str(i), name, fullpath)
        console.print(table)
    else:
        # 用户输入目标文件夹名称列表
        console.print("[yellow]请输入多个目标文件夹名称[/yellow] (每行一个，输入空行结束)")
        target_folder_names = get_multiline_input("请输入多个目标文件夹名称")
        target_folder_fullpaths = None
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
                    for idx, target_name in enumerate(target_folder_names):
                        similarity = get_similarity(subfolder.lower(), target_name.lower())
                        if similarity >= similarity_threshold:
                            folder_info = {
                                "name": subfolder,
                                "path": os.path.join(source_path, subfolder),
                                "target": target_name,
                                "similarity": similarity
                            }
                            # 如果自动获取，补充完整路径
                            if auto_get and target_folder_fullpaths:
                                folder_info["target_fullpath"] = target_folder_fullpaths[idx]
                            similar_folders.append(folder_info)
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
        if auto_get:
            table.add_column("目标完整路径", style="blue")
        for i, folder in enumerate(similar_folders, 1):
            row = [
                str(i),
                folder["name"],
                folder["path"],
                folder["target"],
                f"{folder['similarity']:.2f}"
            ]
            if auto_get:
                row.append(folder.get("target_fullpath", ""))
            table.add_row(*row)
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

        output_paths = []
        for i, folder in enumerate(similar_folders, 1):
            if output_choice == "1":
                # 输出原文件夹路径（自动获取时为完整路径）
                if auto_get and folder.get("path"):
                    out_path = folder["path"]
                else:
                    out_path = folder["path"]
                console.print(f"{i}. ", end="")
                console.print(out_path, markup=False)
                output_paths.append(out_path)
            else:
                # 输出目标文件夹路径
                if auto_get and folder.get("target_fullpath"):
                    target_subfolder = folder["target_fullpath"]
                else:
                    target_subfolder = os.path.join(destination_path, folder["target"])
                destination = os.path.join(target_subfolder, folder["name"])
                console.print(f"{i}. ", end="")
                console.print(destination, markup=False)
                output_paths.append(destination)

        # 写入txt文件
        output_txt = "output_paths.txt"
        try:
            with open(output_txt, "w", encoding="utf-8") as f:
                for p in output_paths:
                    f.write(p + "\n")
            console.print(f"\n[green]路径已写入 {output_txt}，每行一个，便于复制。[/green]")
        except Exception as e:
            console.print(f"[red]写入 {output_txt} 失败: {str(e)}[/red]")
    else:
        console.print("[yellow]未找到符合条件的相似文件夹[/yellow]")

if __name__ == "__main__":
    main()