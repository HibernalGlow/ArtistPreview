"""crashu 配对与内容合并独立包

提供：
1. 相似结果构建标准化配对数据
2. 将配对写入 JSON 文件
3. 按方向移动（合并）两个配对文件夹之一的全部内容到另一方

设计目标：与 crashu 原有扫描逻辑解耦，可独立被其它工具调用。
"""

from .__main__ import PairManager, PairMoveResult, PairRecord

__all__ = ["PairManager", "PairMoveResult", "PairRecord"]
