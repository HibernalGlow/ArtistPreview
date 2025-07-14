# samea

该项目为 `samea`，用于艺术家图片的辅助管理和日志处理。

## 目录结构
- `logs/`：日志文件夹。
- `utils/`：实用工具脚本。

## 用法
主要包含辅助脚本，如 `move_artist_folders.py`。

### 示例命令行用法

#### 移动艺术家文件夹
```bash
python utils/move_artist_folders.py --source 源目录 --target 目标目录 [--dry-run]
```
- `--source`：需要移动的源文件夹路径。
- `--target`：目标文件夹路径。
- `--dry-run`：可选，执行预演，不实际移动文件。

#### 从剪贴板读取目录对批量移动
```bash
python utils/move_artist_folders.py --clipboard [--dry-run]
```
- `--clipboard`：从剪贴板读取路径（每两个为一组，分别为源和目标）。
- `--dry-run`：可选，执行预演，不实际移动文件。

#### 启动 TUI 图形界面
```bash
python utils/move_artist_folders.py
```
无参数时将启动可交互的 TUI 配置界面。

请根据脚本实际参数进行调整。

## 依赖
请参考根目录的 `pyproject.toml`。
