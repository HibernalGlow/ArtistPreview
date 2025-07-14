# previewa

该项目为 `previewa`，用于艺术家图片的预览、分类和流式界面展示。

## 目录结构
- `core/`：核心功能模块。
- `io/`：输入输出相关模块。
- `logs/`：日志文件夹。
- `modes/`：不同模式实现。
- `scripts/`：脚本与数据。
- `ui/`：用户界面，包括 Streamlit 和 CLI。

## 用法
### 启动 Streamlit 界面
```bash
python -m previewa.ui.start_streamlit
```

### 命令行界面
```bash
python -m previewa.ui.cli
```

## 依赖
请参考根目录的 `pyproject.toml`。
