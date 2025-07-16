import os
import difflib
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table

console = Console()

class FolderManager:
    """文件夹管理器"""
    
    @staticmethod
    def get_similarity(s1, s2):
        """计算两个字符串的相似度"""
        return difflib.SequenceMatcher(None, s1, s2).ratio()
    
    @staticmethod
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
    
    @staticmethod
    def auto_get_target_folders(auto_dir):
        """自动获取目标文件夹"""
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
                return None, None
            
            return target_folder_names, target_folder_fullpaths
        except Exception as e:
            console.print(f"[red]自动获取目标文件夹失败: {str(e)}[/red]")
            return None, None
    
    @staticmethod
    def scan_similar_folders(source_paths, target_folder_names, target_folder_fullpaths, similarity_threshold, auto_get):
        """扫描相似文件夹"""
        similar_folders = []
        
        with Progress() as progress:
            task = progress.add_task("[cyan]扫描文件夹...", total=len(source_paths))
            for source_path in source_paths:
                progress.update(task, advance=1, description=f"[cyan]扫描 {source_path}...")
                try:
                    # 获取源文件夹下的一级子文件夹
                    subfolders = [f for f in os.listdir(source_path) if os.path.isdir(os.path.join(source_path, f))]
                    for subfolder in subfolders:
                        for idx, target_name in enumerate(target_folder_names):
                            similarity = FolderManager.get_similarity(subfolder.lower(), target_name.lower())
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
        
        return similar_folders

class UIManager:
    """用户界面管理器"""
    
    @staticmethod
    def show_header():
        """显示程序头部"""
        console.print(Panel("[bold cyan]文件夹相似度检测与批量移动工具[/bold cyan]", border_style="green"))
    
    @staticmethod
    def ask_auto_get():
        """询问是否自动获取目标文件夹"""
        return Confirm.ask("是否自动获取目标文件夹（从指定目录下的一级子目录）？", default=False)
    
    @staticmethod
    def get_auto_dir():
        """获取自动获取目录"""
        return Prompt.ask("请输入用于自动获取目标文件夹的目录", default="E:\\1EHV")
    
    @staticmethod
    def display_target_folders(target_folder_names, target_folder_fullpaths=None):
        """显示目标文件夹"""
        if target_folder_fullpaths:
            table = Table(title="自动获取的目标文件夹")
            table.add_column("序号", justify="center", style="cyan")
            table.add_column("文件夹名称", style="green")
            table.add_column("完整路径", style="blue")
            for i, (name, fullpath) in enumerate(zip(target_folder_names, target_folder_fullpaths), 1):
                table.add_row(str(i), name, fullpath)
        else:
            table = Table(title="目标文件夹名称")
            table.add_column("序号", justify="center", style="cyan")
            table.add_column("文件夹名称", style="green")
            for i, name in enumerate(target_folder_names, 1):
                table.add_row(str(i), name)
        console.print(table)
    
    @staticmethod
    def get_source_paths():
        """获取源文件夹路径"""
        console.print("[yellow]请输入多个源文件夹路径[/yellow] (每行一个，输入空行结束，默认为E:\\1EHV)")
        source_paths = FolderManager.get_multiline_input("请输入多个源文件夹路径")
        if not source_paths:
            source_paths = ["E:\\1EHV"]
        return source_paths
    
    @staticmethod
    def get_destination_path():
        """获取目标文件夹路径"""
        return Prompt.ask("[yellow]请输入目标文件夹路径[/yellow] (默认为E:\\2EHV\\crash)", default="E:\\2EHV\\crash")
    
    @staticmethod
    def get_similarity_threshold():
        """获取相似度阈值"""
        return float(Prompt.ask("[yellow]请输入相似度阈值[/yellow] (0-1之间，默认0.8)", default="0.8"))
    
    @staticmethod
    def display_similar_folders(similar_folders, auto_get):
        """显示找到的相似文件夹"""
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
    
    @staticmethod
    def get_output_choice():
        """获取输出选择"""
        console.print("\n[bold cyan]输出选项：[/bold cyan]")
        console.print("[cyan]1. 输出原文件夹路径[/cyan]")
        console.print("[cyan]2. 输出目标文件夹路径[/cyan]")
        
        return Prompt.ask(
            "[bold yellow]选择输出格式[/bold yellow]",
            choices=["1", "2"],
            default="1"
        )

class OutputManager:
    """输出管理器"""
    
    @staticmethod
    def generate_output_paths(similar_folders, output_choice, destination_path, auto_get):
        """生成输出路径列表"""
        output_paths = []
        console.print("\n[bold green]重复文件夹路径列表：[/bold green]")
        
        for i, folder in enumerate(similar_folders, 1):
            if output_choice == "1":
                # 输出原文件夹路径
                out_path = folder["path"]
                console.print(f"{i}. ", end="")
                console.print(out_path, markup=False)
                output_paths.append(out_path)
            else:
                # 输出目标文件夹路径
                if auto_get and folder.get("target_fullpath"):
                    # 自动获取模式：target_fullpath 就是目标路径，不需要再添加 folder["name"]
                    destination = folder["target_fullpath"]
                else:
                    # 手动输入模式：需要组合 destination_path + target + name
                    target_subfolder = os.path.join(destination_path, folder["target"])
                    destination = os.path.join(target_subfolder, folder["name"])
                console.print(f"{i}. ", end="")
                console.print(destination, markup=False)
                output_paths.append(destination)
        
        return output_paths
    
    @staticmethod
    def save_to_file(output_paths, filename="output_paths.txt"):
        """保存路径到文件"""
        try:
            with open(filename, "w", encoding="utf-8") as f:
                for p in output_paths:
                    f.write(p + "\n")
            console.print(f"\n[green]路径已写入 {filename}，每行一个，便于复制。[/green]")
        except Exception as e:
            console.print(f"[red]写入 {filename} 失败: {str(e)}[/red]")

def main():
    # 显示程序头部
    UIManager.show_header()
    
    # 获取目标文件夹
    auto_get = UIManager.ask_auto_get()
    if auto_get:
        auto_dir = UIManager.get_auto_dir()
        target_folder_names, target_folder_fullpaths = FolderManager.auto_get_target_folders(auto_dir)
        if target_folder_names is None:
            return
        UIManager.display_target_folders(target_folder_names, target_folder_fullpaths)
    else:
        console.print("[yellow]请输入多个目标文件夹名称[/yellow] (每行一个，输入空行结束)")
        target_folder_names = FolderManager.get_multiline_input("请输入多个目标文件夹名称")
        target_folder_fullpaths = None
        UIManager.display_target_folders(target_folder_names)
    
    # 获取用户输入参数
    source_paths = UIManager.get_source_paths()
    destination_path = UIManager.get_destination_path()
    similarity_threshold = UIManager.get_similarity_threshold()
    
    # 创建目标文件夹（如果不存在）
    os.makedirs(destination_path, exist_ok=True)
    
    # 扫描相似文件夹
    similar_folders = FolderManager.scan_similar_folders(
        source_paths, target_folder_names, target_folder_fullpaths, 
        similarity_threshold, auto_get
    )
    
    # 处理结果
    if similar_folders:
        UIManager.display_similar_folders(similar_folders, auto_get)
        output_choice = UIManager.get_output_choice()
        output_paths = OutputManager.generate_output_paths(
            similar_folders, output_choice, destination_path, auto_get
        )
        OutputManager.save_to_file(output_paths)
    else:
        console.print("[yellow]未找到符合条件的相似文件夹[/yellow]")

if __name__ == "__main__":
    main()