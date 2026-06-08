# 雷达波形性能评估软件 V1.0

本项目是一个基于 Python + PySide6 / QtWidgets 的桌面原型软件，用于对雷达波形的探测性能、分辨能力、旁瓣与模糊控制能力、抗干扰性能、反侦察 / 低截获暴露特征和工程可实现性进行结构化评估。

V1.0 的核心定位是“本地算法评估 + 桌面演示闭环”。所有指标计算都在 `radar_eval_core` 中完成，`desktop_app` 只负责参数收集、服务调用、结果展示、报告生成和文件导出。

## 当前版本功能

- 支持 `rect`、`lfm`、`phase_code` 三类复基带波形生成。
- 支持工程指标、零多普勒旁瓣指标、二维模糊函数、Doppler 容忍性、探测性能、宽带高斯噪声压制干扰、LPI 暴露特征、分辨能力和配置化评分。
- 支持命令行完整评估流水线。
- 支持 PySide6 桌面界面：配置、运行评估、查看雷达图、指标表、模糊函数图、频谱图和横向对比。
- 支持本地模板报告，不调用外部 LLM。
- 支持导出 `evaluation_result.json`、`raw_metrics.csv`、`axis_scores.csv`、`chart_data.json`、`report.md` 和 `report.html`。
- 支持 `.rwep.json` 项目文件保存和打开。

## 技术栈

- Python 3.12.x
- PySide6 / QtWidgets
- NumPy / SciPy
- Matplotlib
- Pydantic
- pytest
- ruff
- PyInstaller 预留

## 安装依赖

推荐使用 `uv`：

```powershell
uv python install 3.12
uv sync --python 3.12
```

日常命令可以直接写：

```powershell
uv run pytest
uv run ruff check .
```

## 运行 CLI

```powershell
uv run python scripts/run_eval_cli.py --config configs/lfm_default.json --scoring-config configs/scoring_default.json --output-dir outputs
```

CLI 会输出：

- `request.json`
- `raw_metrics.json`
- `axis_scores.json`
- `evaluation_result.json`
- `chart_data.json`

## 启动桌面软件

```powershell
uv run python -m desktop_app.main
```

启动后可加载默认 LFM 配置，点击“开始评估”，再进入“结果可视化”或“评估报告”页面查看结果。

## 如何生成报告

1. 启动桌面软件。
2. 加载默认配置或打开示例项目。
3. 点击“开始评估”。
4. 进入“评估报告”页面。
5. 点击“生成本地报告”。
6. 可导出 Markdown 或 HTML。

报告只解释 `EvaluationResult` 中已有结构化结果，不计算新指标，不调用外部 API。

## 如何导出结果

运行评估后，在“文件”菜单中选择：

- 导出完整评估 JSON
- 导出原始指标 CSV
- 导出评分 CSV
- 导出图表数据 JSON
- 导出报告 Markdown
- 导出报告 HTML

导出服务只序列化当前结果，不修改 `EvaluationResult`。

## 示例项目

`examples/` 目录提供：

- `examples/lfm_example.rwep.json`
- `examples/phase_code_example.rwep.json`

这些示例可通过桌面软件“文件 / 打开项目”直接打开。示例不包含真实敏感装备参数。

## 当前模型限制

- 不计算截获概率和截获距离比。
- 不实现 CFAR。
- 不实现 Swerling 目标起伏模型。
- 不实现二维 PSLR / ISLR。
- 不实现复杂杂波模型。
- 不实现窄带干扰、扫频干扰、欺骗干扰和干扰识别。
- 不调用外部 LLM 或云端服务。

## 敏感数据注意事项

请勿将真实敏感装备参数、实测数据或涉密场景配置写入示例项目、测试数据、报告或导出文件。本项目当前示例仅用于本地演示和软件功能验证。

