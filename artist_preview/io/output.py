import os
import yaml
from typing import Dict, Any, Optional
from loguru import logger

class OutputHandler:
    """
    输出处理类，负责处理分类结果的输出
    """
    
    def __init__(self):
        pass
    
    def save_to_yaml(self, results: Dict[str, Any], output_file: str) -> bool:
        """
        将分类结果保存到YAML文件
        
        参数:
            results: 分类结果字典
            output_file: 输出文件路径
            
        返回:
            是否成功保存
        """
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump(results, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"分类结果已保存至: {output_file}")
            return True
        except Exception as e:
            logger.error(f"保存分类结果时出错: {e}")
            return False
    
    def print_summary(self, results: Dict[str, Any]) -> None:
        """
        打印分类结果摘要
        
        参数:
            results: 分类结果字典
        """
        total = results.get("total_files", 0)
        classified = results.get("classified", 0)
        unclassified = results.get("unclassified", 0)
        artist_stats = results.get("artist_stats", {})
        
        print("\n===== 分类结果摘要 =====")
        print(f"总文件数: {total}")
        print(f"已分类文件数: {classified}")
        print(f"未分类文件数: {unclassified}")
        
        if artist_stats:
            print("\n画师统计:")
            for artist, count in artist_stats.items():
                print(f"- {artist}: {count} 个文件")
        
        print("=======================\n")
    
    def generate_html_report(self, results: Dict[str, Any], output_file: Optional[str] = None) -> str:
        """
        生成分类结果的HTML报告
        
        参数:
            results: 分类结果字典
            output_file: 输出文件路径，如果为None则不保存到文件
            
        返回:
            HTML内容字符串
        """
        total = results.get("total_files", 0)
        classified = results.get("classified", 0)
        unclassified = results.get("unclassified", 0)
        artist_stats = results.get("artist_stats", {})
        
        # 创建HTML内容
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>画师分类结果</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                .summary {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; }}
                .artist-list {{ margin-top: 20px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
            </style>
        </head>
        <body>
            <h1>画师分类结果</h1>
            
            <div class="summary">
                <h2>摘要</h2>
                <p>总文件数: {total}</p>
                <p>已分类文件数: {classified}</p>
                <p>未分类文件数: {unclassified}</p>
            </div>
            
            <div class="artist-list">
                <h2>画师统计</h2>
                <table>
                    <tr>
                        <th>画师</th>
                        <th>文件数</th>
                    </tr>
        """
        
        # 添加画师统计数据
        for artist, count in artist_stats.items():
            html += f"""
                    <tr>
                        <td>{artist}</td>
                        <td>{count}</td>
                    </tr>
            """
        
        html += """
                </table>
            </div>
        </body>
        </html>
        """
        
        # 保存到文件（如果指定）
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(html)
                logger.info(f"HTML报告已保存至: {output_file}")
            except Exception as e:
                logger.error(f"保存HTML报告时出错: {e}")
        
        return html