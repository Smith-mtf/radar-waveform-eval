# 导出格式 V1.0

## evaluation_result.json

完整评估结果，来自 `EvaluationResult.model_dump(mode="json")`。包含：

- `request`
- `overall_score`
- `axis_scores`
- `raw_metrics`
- `chart_data`
- `summary`

该文件可用于历史结果留档、报告生成和离线复查。

## raw_metrics.csv

原始指标表。字段包括：

- `metric_id`
- `display_name`
- `raw_value`
- `unit`
- `score`
- `axis_id`
- `available`
- `unavailable_reason`

不可用指标的 `raw_value` 为空，原因写入 `unavailable_reason`。

## axis_scores.csv

六维评分表。字段包括：

- `axis_id`
- `display_name`
- `score`
- `weight`
- `available`
- `unavailable_reason`

当前 `EvaluationResult` 不保存评分配置权重，因此导出结果中的 `weight` 为空。

## chart_data.json

图表数据导出。包含波形预览、zero-Doppler cut、zero-delay Doppler cut、模糊函数热力图数据和频谱 PSD 数据。该文件用于结果复查和界面图表重建，不包含完整二维模糊函数矩阵。模糊函数热力图使用完整脉冲时延范围的抽样，显示网格上限为 `257 x 257`，并按波形类型记录 `delay_window_source`、`doppler_window_hz`、`doppler_window_source` 和 `display_model`。当前显示矩阵使用算法核心的离散 FFT 模糊函数定义。

## report.md

本地模板报告 Markdown。报告只解释已有结构化结果，不计算新指标。

## report.html

本地模板报告 HTML。使用基础内联 CSS，不依赖外部模板引擎。
