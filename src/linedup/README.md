# 行去重工具 使用说明

**功能**：

- 对比 test/source.txt 和 test/filter.txt 两个文件内容，若 source.txt 某行包含 filter.txt 任意一行，则该行会被移除。
- 结果输出到 test/output.txt。

**用法**：

1. 将待处理的源文件命名为 `source.txt`，过滤内容命名为 `filter.txt`，放入本包下的 `test` 目录。
2. 运行本脚本：

```bash
python -m linedup
```

3. 处理结果会输出到 `test/output.txt`。

**注意事项**：

- 文件需为 UTF-8 编码。
- 运行过程中会有详细的交互式进度和统计信息。
- 若 `test` 目录不存在会自动创建。
