"""
ArtistPreview - 漫画/插图作品按画师分类工具

提供多种分类模式:
- 标准模式: 直接将文件分类到对应画师目录
- 中间模式: 将文件移动到中间目录，可选是否创建画师子文件夹
- 文本模式: 生成分类结果YAML，不移动文件
"""

__version__ = "0.1.0"

from .main import ArtistPreviewController, main

__all__ = ["ArtistPreviewController", "main"]