"""
文件夹管理器模块
负责文件夹相关的核心逻辑处理（高性能优化版）
"""
import os
import difflib
from functools import lru_cache
from rich.console import Console
from rich.progress import Progress
from lista.core.service import extract_names_from_folder_name

# 可选高性能相似度库（若不可用则回退 difflib）
try:
    from rapidfuzz import fuzz as _rf_fuzz  # type: ignore
except Exception:  # pragma: no cover - 可用则用
    _rf_fuzz = None

console = Console()


class FolderManager:
    """文件夹管理器"""
    
    @staticmethod
    def get_similarity(s1: str, s2: str) -> float:
        """计算两个字符串的相似度（仍保留 API 以兼容旧代码）。"""
        return _similarity_ratio_cached(s1.lower(), s2.lower())
    
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

        # 预处理：目标列表小写与别名列表（降低重复解析与小写转换开销）
        targets_prepared = []  # [(idx, target_name, target_lower, [aliases_lower], {lower: original})]
        for idx, t in enumerate(target_folder_names):
            t_lower = t.lower()
            t_aliases = extract_names_from_folder_name(t)
            t_aliases_lower = [a.lower() for a in t_aliases]
            tgt_alias_map = {a.lower(): a for a in t_aliases}
            targets_prepared.append((idx, t, t_lower, t_aliases_lower, tgt_alias_map))
        
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
                        sub_lower = subfolder.lower()

                        # 先准备源解析得到的别名（回退匹配用，小写）
                        src_names = extract_names_from_folder_name(subfolder)
                        src_aliases_lower = [a.lower() for a in src_names]
                        src_alias_map = {a.lower(): a for a in src_names}

                        for idx, target_name, tgt_lower, tgt_aliases_lower, tgt_alias_map in targets_prepared:
                            # 快速相等短路（避免进入相似度算法）
                            if sub_lower == tgt_lower:
                                best_similarity = 1.0
                                best_kind = "full/full"
                                best_src_hit = subfolder
                                best_tgt_hit = target_name
                                matched = True
                            else:
                                # 长度上界剪枝：若理论最大相似度都低于阈值，直接跳过
                                if _max_possible_ratio(len(sub_lower), len(tgt_lower)) < similarity_threshold:
                                    best_similarity = 0.0
                                    matched = False
                                    best_kind = "full/full"
                                    best_src_hit = subfolder
                                    best_tgt_hit = target_name
                                else:
                                    # 1) 优先：完整文件夹名直接相似度（带缓存/可选 rapidfuzz）
                                    best_similarity = _similarity_ratio_cached(sub_lower, tgt_lower)
                                    best_kind = "full/full"
                                    best_src_hit = subfolder
                                    best_tgt_hit = target_name
                                    matched = best_similarity >= similarity_threshold

                            # 2) 回退：使用名字列表交叉比对（别名对全称、全称对别名、别名对别名）
                            if not matched:
                                # 源别名 vs 目标全称
                                for s in src_aliases_lower:
                                    if _max_possible_ratio(len(s), len(tgt_lower)) < similarity_threshold:
                                        continue
                                    sim = _similarity_ratio_cached(s, tgt_lower)
                                    if sim > best_similarity:
                                        best_similarity = sim
                                        best_kind = "alias/full"
                                        best_src_hit = src_alias_map.get(s, s)
                                        best_tgt_hit = target_name
                                # 目标别名 vs 源全称
                                for t in tgt_aliases_lower:
                                    if _max_possible_ratio(len(sub_lower), len(t)) < similarity_threshold:
                                        continue
                                    sim = _similarity_ratio_cached(sub_lower, t)
                                    if sim > best_similarity:
                                        best_similarity = sim
                                        best_kind = "full/alias"
                                        best_src_hit = subfolder
                                        best_tgt_hit = tgt_alias_map.get(t, t)
                                # 源别名 vs 目标别名
                                for s in src_aliases_lower:
                                    for t in tgt_aliases_lower:
                                        if _max_possible_ratio(len(s), len(t)) < similarity_threshold:
                                            continue
                                        sim = _similarity_ratio_cached(s, t)
                                        if sim > best_similarity:
                                            best_similarity = sim
                                            best_kind = "alias/alias"
                                            best_src_hit = src_alias_map.get(s, s)
                                            best_tgt_hit = tgt_alias_map.get(t, t)
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


# --- 内部：高性能相似度工具 ---
@lru_cache(maxsize=100_000)
def _similarity_ratio_cached(s1_lower: str, s2_lower: str) -> float:
    if s1_lower == s2_lower:
        return 1.0
    if _rf_fuzz is not None:
        # rapidfuzz 的 ratio 返回 0..100
        return _rf_fuzz.ratio(s1_lower, s2_lower) / 100.0
    return difflib.SequenceMatcher(None, s1_lower, s2_lower).ratio()


def _max_possible_ratio(len1: int, len2: int) -> float:
    """给定长度的相似度上界：2*min/(len1+len2)。若小于阈值可提前剪枝。"""
    if len1 == 0 and len2 == 0:
        return 1.0
    if len1 == 0 or len2 == 0:
        return 0.0
    m = min(len1, len2)
    return 2.0 * m / (len1 + len2)
