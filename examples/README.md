# 示例项目

本目录提供 V1.0 演示用 `.rwep.json` 项目文件：

- `lfm_example.rwep.json`：LFM 波形示例。
- `phase_code_example.rwep.json`：二相相位编码波形示例。

这些示例来自默认仿真配置，用于软件演示和回归验证，不包含真实敏感装备参数。

使用方式：

1. 启动桌面软件：`uv run python -m desktop_app.main`
2. 在菜单中选择“文件 / 打开项目”。
3. 打开本目录中的任一 `.rwep.json` 文件。
4. 进入“运行评估”页面，点击“开始评估”。

示例项目不预置评估结果；打开后由本地算法流水线重新计算。

