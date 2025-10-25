"""压缩包分类移动工具主入口"""
import sys
import os

# 检查是否在 streamlit 环境中运行
def is_streamlit_running():
    """检测是否在 Streamlit 环境中运行"""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except ImportError:
        # streamlit 未安装或版本较旧
        pass
    
    # 备用检测：检查是否通过 streamlit 命令启动
    return any('streamlit' in arg.lower() for arg in sys.argv)

# 如果在 streamlit 环境中，直接运行 streamlit 代码
if is_streamlit_running() or (len(sys.argv) > 1 and 'streamlit' in ' '.join(sys.argv).lower()):
    import streamlit as st
    
    # 处理相对导入问题
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    # 导入模块
    from movea.ui import render_sidebar, render_main_interface

    # 设置页面配置
    st.set_page_config(
        page_title="压缩包分类移动工具",
        page_icon="📦",
        layout="wide",  # 开启宽屏模式
        initial_sidebar_state="expanded"
    )

    st.title("压缩包分类移动工具")

    # 渲染侧边栏并获取配置
    root_path, regex_patterns, scan_button, show_full_names, items_per_page = render_sidebar()

    # 渲染主界面
    render_main_interface(scan_button, root_path, regex_patterns, show_full_names, items_per_page)

else:
    # 命令行启动模式 - 启动 lata
    import subprocess
    from pathlib import Path

    def main():
        """主函数 - 尝试启动 lata 交互式任务选择器"""
        try:
            script_dir = Path(__file__).parent
            result = subprocess.run("lata", cwd=script_dir)
            sys.exit(result.returncode)
        except FileNotFoundError:
            print("\n压缩包分类移动工具")
            print("=" * 50)
            print("未找到 'lata' 命令。请使用以下方式之一:\n")
            print("  1. 安装 lata: pip install lata")
            print("     然后运行: lata")
            print("\n  2. 直接使用 streamlit 启动")
            print("     cd src/movea && streamlit run __main__.py")
            print("\n  3. 使用 task 命令")
            print("     cd src/movea && task start")
            print("=" * 50)
            sys.exit(1)
        except Exception as e:
            print(f"启动 lata 失败: {e}")
            sys.exit(1)

    if __name__ == "__main__":
        main()