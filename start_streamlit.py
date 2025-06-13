#!/usr/bin/env python3
"""
启动Streamlit应用的脚本
"""
import subprocess
import sys
import os
from pathlib import Path

def install_requirements():
    """安装依赖"""
    requirements_file = Path(__file__).parent / "requirements_streamlit.txt"
    if requirements_file.exists():
        print("正在安装依赖...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)])
    else:
        print("requirements_streamlit.txt 文件不存在，跳过依赖安装")

def start_streamlit():
    """启动Streamlit应用"""
    app_file = Path(__file__).parent / "src" / "previewa" / "scripts" / "artist_preview_streamlit.py"
    
    if not app_file.exists():
        print(f"应用文件不存在: {app_file}")
        return
    
    print(f"启动Streamlit应用: {app_file}")
    
    # 设置环境变量
    env = os.environ.copy()
    env['STREAMLIT_SERVER_PORT'] = '8501'
    env['STREAMLIT_SERVER_ADDRESS'] = 'localhost'
    
    # 启动应用
    cmd = [
        sys.executable, "-m", "streamlit", "run", str(app_file),
        "--server.port", "8501",
        "--server.address", "localhost",
        "--browser.gatherUsageStats", "false"
    ]
    
    subprocess.run(cmd, env=env)

if __name__ == "__main__":
    try:
        # 安装依赖
        install_requirements()
        
        # 启动应用
        start_streamlit()
        
    except KeyboardInterrupt:
        print("\n应用已停止")
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)
