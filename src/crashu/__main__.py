"""
文件夹相似度检测与批量移动工具
主入口模块
"""
from .core.app_controller import AppController


def main():
    """主函数"""
    app = AppController()
    app.run()


if __name__ == "__main__":
    main()