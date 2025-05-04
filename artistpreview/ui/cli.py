import argparse
from typing import Any
from loguru import logger

def parse_args() -> argparse.Namespace:
    """
    解析命令行参数
    
    返回:
        解析后的参数命名空间
    """
    parser = argparse.ArgumentParser(
        description='ArtistPreview - 漫画/插图作品按画师分类工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 路径来源选项，互斥组
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument('-c', '--clipboard', action='store_true',
                         help='使用剪贴板中的路径')
    source_group.add_argument('-p', '--path', type=str,
                         help='指定待处理文件或文件夹路径')
    
    # 分类模式选项
    parser.add_argument('--intermediate', action='store_true',
                        help='启用中间模式，将文件移动到中间目录')
    parser.add_argument('--create-folders', action='store_true',
                        help='在中间模式下创建画师文件夹')
    parser.add_argument('--output-dir', type=str,
                        help='指定输出目录')
    
    # 文本模式选项
    parser.add_argument('--text-mode', action='store_true',
                        help='启用文本模式，从文本文件中读取路径列表')
    parser.add_argument('--text-file', type=str, default='to_be_classified.txt',
                        help='文本模式下的输入文件路径 (默认: to_be_classified.txt)')
    parser.add_argument('--output-file', type=str, default='classified_result.yaml',
                        help='文本模式下的输出文件路径 (默认: classified_result.yaml)')
    
    # 其他选项
    parser.add_argument('--update-list', action='store_true',
                        help='更新画师列表')
    parser.add_argument('--cache-file', type=str,
                        help='指定画师缓存文件路径')
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help='增加输出详细程度')
    parser.add_argument('--gui', action='store_true',
                        help='启动图形界面')
    
    return parser.parse_args()

