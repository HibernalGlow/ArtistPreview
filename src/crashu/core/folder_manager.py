"""
文件夹管理器模块
负责文件夹相关的核心逻辑处理
"""
import os
import difflib
from rich.console import Console
from rich.progress import Progress
from lista.core.service import extract_names_from_folder_name

console = Console()


class FolderManager:
    """文件夹管理器"""
    
    @staticmethod
    def get_similarity(s1: str, s2: str) -> float:
        """
        计算两个字符串的相似度
        
        Args:
            s1: 第一个字符串
            s2: 第二个字符串
            
        Returns:
            相似度值 (0-1之间)
        """
        return difflib.SequenceMatcher(None, s1, s2).ratio()
    
    @staticmethod
    def get_multiline_input(prompt_message: str) -> list[str]:
        """
        获取多行输入，空行结束
        
        Args:
            prompt_message: 提示信息
            
        Returns:
            输入的行列表
        """
        console.print(f"[yellow]{prompt_message}[/yellow] (输入空行结束)")
        lines = []
        while True:
            line = input()
            if not line.strip():
                break
            lines.append(line.strip())
        return lines
    
    @staticmethod
    def auto_get_target_folders(auto_dir: str) -> tuple[list[str], list[str]] | tuple[None, None]:
        """
        自动获取目标文件夹
        
        Args:
            auto_dir: 自动获取的目录路径
            
        Returns:
            (目标文件夹名称列表, 目标文件夹完整路径列表) 或 (None, None)
        """
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
    def scan_similar_folders(
        source_paths: list[str], 
        target_folder_names: list[str], 
        target_folder_fullpaths: list[str] | None, 
        similarity_threshold: float, 
        auto_get: bool
    ) -> list[dict]:
        """
        扫描相似文件夹
        
        Args:
            source_paths: 源文件夹路径列表
            target_folder_names: 目标文件夹名称列表
            target_folder_fullpaths: 目标文件夹完整路径列表
            similarity_threshold: 相似度阈值
            auto_get: 是否自动获取模式
            
        Returns:
            相似文件夹信息列表
        """
        similar_folders = []
        
        with Progress() as progress:
            task = progress.add_task("[cyan]扫描文件夹...", total=len(source_paths))
            
            for source_path in source_paths:
                progress.update(task, advance=1, description=f"[cyan]扫描 {source_path}...")
                
                try:
                    # 获取源文件夹下的一级子文件夹
                    subfolders = [
                        f for f in os.listdir(source_path) 
                        if os.path.isdir(os.path.join(source_path, f))
                    ]
                    
                    for subfolder in subfolders:
                        subfolder_path = os.path.join(source_path, subfolder)
                        # 先准备源/目标解析得到的名字（作为回退匹配用）
                        src_names = extract_names_from_folder_name(subfolder)
                        for idx, target_name in enumerate(target_folder_names):
                            # 1) 优先：完整文件夹名直接相似度
                            best_similarity = FolderManager.get_similarity(
                                subfolder.lower(),
                                target_name.lower(),
                            )
                            best_kind = "full/full"
                            best_src_hit = subfolder
                            best_tgt_hit = target_name
                            matched = best_similarity >= similarity_threshold

                            # 2) 回退：使用名字列表交叉比对（源解析名 vs 目标完整名；以及若目标名也可解析则互相比对）
                            if not matched:
                                tgt_names = extract_names_from_folder_name(target_name)
                                # 源解析名与目标完整名
                                for s in src_names:
                                    sim = FolderManager.get_similarity(s.lower(), target_name.lower())
                                    if sim > best_similarity:
                                        best_similarity = sim
                                        best_kind = "alias/full"
                                        best_src_hit = s
                                        best_tgt_hit = target_name
                                # 目标解析名与源完整名
                                for t in tgt_names:
                                    sim = FolderManager.get_similarity(subfolder.lower(), t.lower())
                                    if sim > best_similarity:
                                        best_similarity = sim
                                        best_kind = "full/alias"
                                        best_src_hit = subfolder
                                        best_tgt_hit = t
                                # 源解析名与目标解析名逐两比较
                                for s in src_names:
                                    for t in tgt_names:
                                        sim = FolderManager.get_similarity(s.lower(), t.lower())
                                        if sim > best_similarity:
                                            best_similarity = sim
                                            best_kind = "alias/alias"
                                            best_src_hit = s
                                            best_tgt_hit = t
                                matched = best_similarity >= similarity_threshold

                            if matched:
                                folder_info = {
                                    "name": subfolder,
                                    "path": subfolder_path,
                                    "target": target_name,
                                    "similarity": best_similarity,
                                    # 匹配元数据
                                    "match_dim": best_kind,
                                    "match_src": best_src_hit,
                                    "match_tgt": best_tgt_hit,
                                }
                                if auto_get and target_folder_fullpaths:
                                    folder_info["target_fullpath"] = target_folder_fullpaths[idx]
                                similar_folders.append(folder_info)
                                
                except Exception as e:
                    console.print(f"[bold red]扫描 {source_path} 时出错: {str(e)}[/bold red]")
        
        return similar_folders
