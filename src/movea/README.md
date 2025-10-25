# Movea - 压缩包分类移动工具

基于 Streamlit 的交互式压缩包分类和移动工具。

## 功能特点

- 📂 扫描目录中的压缩包文件
- 🔍 使用正则表达式匹配文件夹
- 🚀 批量移动文件到对应文件夹
- 🎨 直观的 Web UI 界面
- 📋 支持黑名单过滤

## 使用方式

### 1. 通过命令直接启动（推荐）

```bash
movea
```

运行后会自动启动 `lata` 交互式任务选择器，您可以从中选择：
- **start**: 启动 Streamlit Web 界面
- **start-browser**: 启动并自动打开浏览器
- **start-port**: 在指定端口启动
- **ready**: 运行准备工作流

### 2. 使用 lata 交互式选择

在 movea 目录下运行：

```bash
lata
```

### 3. 直接使用 task 命令

```bash
# 启动 Streamlit UI
task start

# 启动并自动打开浏览器
task start-browser

# 在指定端口启动
task start-port PORT=8502

# 查看所有可用任务
task --list
```

### 4. 直接使用 streamlit 命令

```bash
streamlit run movea/__main__.py
```

## 配置文件

- `config.toml`: 主配置文件
- `Taskfile.yml`: 任务定义文件

## 工作流程

1. 在侧边栏配置根目录和正则表达式模式
2. 点击"扫描"按钮扫描目录
3. 查看扫描结果并预览待移动文件
4. 确认后执行移动操作

## 注意事项

- 移动操作是不可逆的，请谨慎操作
- 建议先使用小范围测试
- 支持文件夹黑名单功能

## 依赖项

- streamlit
- 其他依赖见 pyproject.toml

