"""压缩包分类移动工具主入口"""
import streamlit as st
import sys
import os

# 处理相对导入问题
if __name__ == "__main__":
    # 如果是直接运行此文件，添加父目录到路径
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    # 导入模块
    from movea.ui import render_sidebar, render_main_interface
else:
    # 如果是作为模块导入，使用相对导入
    from .ui import render_sidebar, render_main_interface

def main():
    """主函数"""
    st.title("压缩包分类移动工具")

    # 渲染侧边栏并获取配置
    root_path, regex_patterns, scan_button, show_full_names, items_per_page = render_sidebar()

    # 渲染主界面
    render_main_interface(scan_button, root_path, regex_patterns, show_full_names, items_per_page)

if __name__ == "__main__":
    main()