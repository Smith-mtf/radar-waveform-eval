# 指标体系 V1.0

本文只介绍当前软件评估界面和默认评分配置中保留的代表性指标。部分辅助指标虽由
`radar_eval_core` 计算并保存在 `EvaluationResult.raw_metrics` 中，但不作为本文件的
重点指标展开。

## 波形参数定义

当前支持 `rect`、`lfm`、`phase_code` 三类复基带波形。`sample_rate_hz` 是复基带
IQ 离散采样率，只约束时间轴和可表示频率范围，不等同于名义带宽。

### rect

矩形脉冲的名义带宽不手填，按 `bandwidth_hz = 1 / pulse_width_s` 派生。

### lfm

线性调频脉冲使用显式扫频带宽 `bandwidth_hz`。调频率为
`k = bandwidth_hz / pulse_width_s`，复基带相位为
`phi(t) = pi * k * (t - pulse_width_s / 2)^2`。

### phase_code

二相相位编码支持 `-1/1` 或 `0/1` 输入，生成时统一转换为 `-1/1`。配置中的
`pulse_width_s` 表示单个子脉冲/码片宽度，名义带宽按码片率
`bandwidth_hz = 1 / pulse_width_s` 派生。完整编码脉冲时宽为
`code_length * pulse_width_s`。

## 代表性指标清单

| 维度 | 指标 ID | 指标名称 |
| --- | --- | --- |
| 探测性能 | `detection.pd` | 检测概率 |
| 探测性能 | `detection.output_snr_db` | 匹配滤波输出 SNR |
| 分辨能力 | `resolution.range_resolution_m` | 距离分辨率 |
| 分辨能力 | `resolution.velocity_resolution_mps` | 速度分辨率 |
| 旁瓣与模糊控制 | `sidelobe_ambiguity.zero_doppler_pslr_db` | 零多普勒 PSLR |
| 旁瓣与模糊控制 | `sidelobe_ambiguity.zero_doppler_islr_db` | 零多普勒 ISLR |
| 旁瓣与模糊控制 | `sidelobe_ambiguity.doppler_tolerance_hz` | 多普勒容忍性 |
| 抗干扰性能 | `anti_jamming.jammed_pd` | 干扰下检测概率 |
| 抗干扰性能 | `anti_jamming.pd_retention` | 检测概率保持率 |
| 低截获暴露特征 | `lpi.nominal_avg_psd_w_per_hz` | 名义平均功率谱密度 |

## 探测性能

探测性能使用单脉冲匹配滤波平方律检测模型。噪声为复高斯白噪声，检测统计量为
`T = |y|^2 / (sigma^2 * Es)`，其中 `Es = sum(abs(s)^2)`。

### 检测概率

- 指标 ID：`detection.pd`
- 定义：`scipy.stats.ncx2.sf(2 * threshold, df=2, nc=2 * output_snr_linear)`
- 单位：无量纲。
- 指标方向：越大越好。

### 匹配滤波输出 SNR

- 指标 ID：`detection.output_snr_db`
- 定义：`10 * log10(Es / noise_variance)`
- 单位：dB。
- 指标方向：越大越好。

## 分辨能力

### 距离分辨率

- 指标 ID：`resolution.range_resolution_m`
- 定义：`c / (2 * bandwidth_hz)`
- 单位：m。
- 指标方向：越小越好。

### 速度分辨率

- 指标 ID：`resolution.velocity_resolution_mps`
- 定义：载波波长除以两倍相干处理时间。
- 单位：m/s。
- 指标方向：越小越好。
- 适用条件：需要载频和严格定义的 CPI。

## 旁瓣与模糊控制

零多普勒旁瓣指标基于发射信号的自匹配滤波输出。主瓣范围由 `MainlobeSpec`
显式定义，默认配置使用 `first_local_minimum`。

### 零多普勒 PSLR

- 指标 ID：`sidelobe_ambiguity.zero_doppler_pslr_db`
- 定义：主瓣外最大旁瓣幅度与主峰幅度之比，
  `20 * log10(A_side / A_main)`
- 单位：dB。
- 指标方向：越低越好。
- 不可用条件：按 `MainlobeSpec` 不能严格确定主瓣边界时不可用。

### 零多普勒 ISLR

- 指标 ID：`sidelobe_ambiguity.zero_doppler_islr_db`
- 定义：主瓣外旁瓣能量与主瓣能量之比，
  `10 * log10(E_side / E_main)`
- 单位：dB。
- 指标方向：越低越好。
- 说明：ISLR 衡量旁瓣总能量，和 PSLR 的“最大单个旁瓣”互补。ISLR 通常会比
  PSLR 更接近 0 dB，因为它累加了全部主瓣外旁瓣能量。
- 不可用条件：按 `MainlobeSpec` 不能严格确定主瓣边界时不可用；例如默认
  `first_local_minimum` 定义下，矩形脉冲自相关为单调三角形，没有可分离的局部极小值，
  因此不输出猜测值。

### 多普勒容忍性

- 指标 ID：`sidelobe_ambiguity.doppler_tolerance_hz`
- 定义：在 zero-delay Doppler cut 上，响应下降到
  `10^(-doppler_loss_db / 20)` 时正负 crossing 绝对值的较小者。
- 单位：Hz。
- 指标方向：越大越好。

## 抗干扰性能

抗干扰指标基于宽带复高斯噪声压制干扰模型。干扰被视为与热噪声独立的额外白噪声，
总扰动方差为 `noise_variance + jammer_variance`。

### 干扰下检测概率

- 指标 ID：`anti_jamming.jammed_pd`
- 定义：使用总扰动方差计算的检测概率。
- 单位：无量纲。
- 指标方向：越大越好。

### 检测概率保持率

- 指标 ID：`anti_jamming.pd_retention`
- 定义：干扰下检测概率与无干扰检测概率的比值。
- 单位：无量纲。
- 指标方向：越大越好。

## 低截获暴露特征

### 名义平均功率谱密度

- 指标 ID：`lpi.nominal_avg_psd_w_per_hz`
- 定义：波形平均功率除以名义带宽。
- 单位：W/Hz。
- 说明：这是名义值，不是 periodogram 的逐频点 PSD。
- 指标方向：通常越小越有利于低截获设计。

## 评分输出

评分模块根据 `ScoringConfig` 中显式配置的归一化边界、方向和权重计算百分制得分。

- 维度得分输出：`EvaluationResult.axis_scores`
- 综合得分输出：`EvaluationResult.overall_score`
- 不可用指标不会按 0 分处理；没有可用评分指标的维度会标记为不可用。
- 默认评分配置不包含工程可实现性评分。

### 综合评估逻辑

一次完整评估先由 `radar_eval_core.evaluation_pipeline.compute_waveform_evaluation`
生成结构化原始指标 `EvaluationResult.raw_metrics`。评分模块不会重新计算雷达指标，
只读取 `raw_metrics` 中已有的数值，并按 `ScoringConfig` 中启用的评分项执行归一化和加权。

综合评估分三步：

1. 单指标归一化。
   每个启用的 `MetricScoreConfig` 根据 `metric_id` 找到对应 `RawMetric`，将原始值转换为
   `0..100` 的单指标得分。
2. 维度得分计算。
   同一 `axis_id` 下可用的单指标得分按指标权重做加权平均，形成
   `AxisScore.score`。
3. 综合得分计算。
   所有可用维度按维度权重做加权平均，形成 `EvaluationResult.overall_score`。

单指标归一化规则：

- `higher_better`：值越大越好。`min_value` 对应 0 分，`max_value` 对应 100 分，
  中间线性插值，超出边界后截断到 `0..100`。
- `lower_better`：值越小越好。`min_value` 对应 100 分，`max_value` 对应 0 分，
  中间线性插值，超出边界后截断到 `0..100`。
- `target_range`：目标区间内为 100 分。低于 `target_min` 时在
  `min_value..target_min` 之间线性上升；高于 `target_max` 时在
  `target_max..max_value` 之间线性下降。

维度得分公式：

```text
axis_score = sum(metric_score_i * metric_weight_i) / sum(metric_weight_i)
```

综合得分公式：

```text
overall_score = sum(axis_score_j * axis_weight_j) / sum(axis_weight_j)
```

不可用处理规则：

- 如果 `RawMetric.available = false` 或 `RawMetric.value = null`，该指标不参与维度得分。
- 如果评分配置中启用的指标在 `raw_metrics` 中不存在，该指标也不参与维度得分，并记录原因。
- 如果某个维度没有任何可用评分指标，该维度标记为 unavailable，不给伪造 0 分。
- 综合得分只使用可用维度；不可用维度不会按 0 分计入总分。
- 如果没有任何可用维度，评分模块会报错，而不是返回猜测得分。

默认权重配置来自 `configs/scoring_default.json`。当前默认综合评估包含 5 个维度，
各维度权重均为 `1.0`。当 5 个维度都可用时，综合得分等价于 5 个维度得分的等权平均：

```text
overall_score = (
    detection_score
  + resolution_score
  + sidelobe_ambiguity_score
  + anti_jamming_score
  + lpi_score
) / 5
```

各维度内部先把原始指标归一化为 `0..100` 的单指标得分，再按指标权重加权。
记 `score(metric_id)` 为某个指标归一化后的百分制得分，默认维度得分如下：

```text
detection_score =
    (
        2.0 * score(detection.pd)
      + 1.0 * score(detection.output_snr_db)
    ) / 3.0

resolution_score =
    (
        2.0 * score(resolution.range_resolution_m)
      + 1.0 * score(resolution.velocity_resolution_mps)
    ) / 3.0

sidelobe_ambiguity_score =
    (
        1.0 * score(sidelobe_ambiguity.zero_doppler_pslr_db)
      + 1.0 * score(sidelobe_ambiguity.zero_doppler_islr_db)
      + 1.0 * score(sidelobe_ambiguity.doppler_tolerance_hz)
    ) / 3.0

anti_jamming_score =
    (
        1.0 * score(anti_jamming.jammed_pd)
      + 2.0 * score(anti_jamming.pd_retention)
    ) / 3.0

lpi_score =
    score(lpi.nominal_avg_psd_w_per_hz)
```

也就是说，默认配置下：

- 综合层面：探测、分辨、旁瓣与模糊控制、抗干扰、低截获 5 个维度等权。
- 探测维度：检测概率 `detection.pd` 的权重是输出信噪比的 2 倍。
- 分辨维度：距离分辨率的权重是速度分辨率的 2 倍。
- 旁瓣与模糊控制维度：峰值旁瓣比、积分旁瓣比、多普勒容限等权。
- 抗干扰维度：检测概率保持率 `anti_jamming.pd_retention` 的权重是干扰下检测概率的 2 倍。
- 低截获维度：当前只使用名义平均功率谱密度一个代表性指标。

如果某个指标不可用，它会从所在维度的分子和分母中同时移除，剩余可用指标按原权重重新归一。
例如矩形脉冲在当前主瓣定义下可能没有可用的峰值旁瓣比和积分旁瓣比，
则旁瓣与模糊控制维度只用剩余可用指标计算；如果该维度没有任何可用指标，
整个维度不参与综合得分。

默认综合得分是当前演示评分配置下的相对评分，依赖归一化边界、方向和权重设置；
它不是独立于任务场景和评分配置的绝对物理结论。

## 适用条件

- 当前信号均按复基带 IQ 表达。
- 功率类指标直接基于离散 IQ 样本计算。
- 当 IQ 幅度按 `sqrt(W)` 标定时，`abs(iq)^2` 可解释为 W。
- `phase_code` 要求单个子脉冲采样点数为整数。
- 指标计算在 `radar_eval_core` 中完成；报告和导出服务只解释或序列化已有结果。
