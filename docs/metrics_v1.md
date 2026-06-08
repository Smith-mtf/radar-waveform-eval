# 指标体系 V1.0

V1.0 建立波形定义、数据结构、基础工程指标、零多普勒自相关旁瓣指标、离散非周期二维模糊函数、单脉冲匹配滤波平方律检测模型，以及宽带复高斯噪声压制干扰模型。当前范围不包含距离-多普勒耦合指标、CFAR、杂波模型或复杂电磁环境仿真。

## 波形定义

### rect

`rect` 表示复基带矩形脉冲。IQ 幅度为 `sqrt(peak_power_w)`，相位为 0。当 IQ 幅度按 `sqrt(W)` 标定时，`mean(abs(iq)^2)` 对应平均功率，单位为 W。

### lfm

`lfm` 表示复基带线性调频脉冲。时间轴定义为 `t = arange(total_samples) / sample_rate_hz`，中心化时间定义为 `t_centered = t - pulse_width_s / 2`。调频率为 `k = bandwidth_hz / pulse_width_s`，相位为 `phi(t) = pi * k * t_centered^2`。该定义对应复基带瞬时频率从约 `-bandwidth_hz / 2` 扫到 `+bandwidth_hz / 2`。

### phase_code

`phase_code` 表示二相相位编码复基带脉冲。输入码序列可以是 `-1/1` 或 `0/1`，生成时统一转换为 `-1/1`：`1` 表示相位 0，`-1` 表示相位 pi。`total_samples = sample_rate_hz * pulse_width_s` 必须为整数，并且必须能被 `code_length` 整除。

## 工程指标定义

### 平均功率

- 指标含义：描述复 IQ 信号在采样窗口内的平均功率水平。
- 计算公式：`average_power = mean(abs(iq)^2)`。
- 单位：取决于 IQ 标定；当 IQ 幅度按 `sqrt(W)` 标定时，单位为 W。
- 指标方向：需要结合发射功率约束、探测需求和低截获需求解释。

### 峰值功率

- 指标含义：描述复 IQ 信号在采样窗口内的最大瞬时功率。
- 计算公式：`peak_power = max(abs(iq)^2)`。
- 单位：取决于 IQ 标定；当 IQ 幅度按 `sqrt(W)` 标定时，单位为 W。
- 指标方向：用于检查峰值发射能力约束，过高会增加硬件实现压力。

### PAPR

- 指标含义：峰均功率比，描述峰值功率相对平均功率的比例。
- 计算公式：`PAPR_dB = 10 * log10(peak_power / average_power)`。
- 单位：dB。
- 指标方向：通常越低越有利于功放效率和工程实现。

### TBP

- 指标含义：时间带宽积，描述名义带宽和脉宽的乘积。
- 计算公式：`TBP = bandwidth_hz * pulse_width_s`。
- 单位：无量纲。
- 指标方向：需要结合处理方式、硬件带宽和任务约束解释。

### 名义平均 PSD

- 指标含义：在给定带宽内功率均匀分布条件下的名义平均功率谱密度。
- 计算公式：`nominal_avg_psd = average_power_w / bandwidth_hz`。
- 单位：W/Hz。
- 指标方向：在平均功率不变时，名义平均 PSD 越低通常越有利于低截获设计，但必须结合探测性能解释。

## 匹配滤波与零多普勒旁瓣指标

### 匹配滤波输出

- 指标含义：接收信号经发射信号匹配滤波后的离散时间线性卷积输出。
- 离散匹配滤波器：`h[n] = conj(tx[::-1])`。
- 计算方式：`y[n] = convolve(rx, h, mode="full")`。
- 关系说明：在相同采样和归一化约定下，`tx` 的自匹配滤波输出与 zero-Doppler cut 等价。

### 零多普勒 PSLR

- 指标名称：`zero_doppler_pslr_db`。
- 指标含义：零多普勒自相关主峰幅度与主瓣区域外最大旁瓣幅度的比值。
- 计算公式：`20 * log10(A_side / A_main)`。
- 单位：dB。
- 指标方向：越低越好。
- 边界要求：主瓣区域必须由 `MainlobeSpec` 显式定义。

### 零多普勒 ISLR

- 指标名称：`zero_doppler_islr_db`。
- 指标含义：零多普勒自相关旁瓣总能量与主瓣能量的比值。
- 计算公式：`10 * log10(E_side / E_main)`。
- 单位：dB。
- 指标方向：越低越好。
- 边界要求：该指标对主瓣边界敏感，主瓣区域必须由 `MainlobeSpec` 显式定义。

### 主瓣宽度

- 指标名称：`mainlobe_width_samples`。
- 指标含义：主瓣左右闭区间包含的采样点数。
- 计算公式：`mainlobe_width_samples = right - left + 1`。
- 单位：samples。
- 指标方向：通常越小越好，但必须结合距离分辨率和旁瓣指标解释。

## 二维模糊函数与多普勒容忍性

### 二维模糊函数

- 指标名称：`ambiguity_function`。
- 定义：`chi[m, fd] = sum_n s[n] * conj(s[n - m]) * exp(-j * 2*pi * fd * n * Ts)`。
- 相关类型：非周期相关，超出信号支撑范围的样本不参与求和。
- delay 单位：samples 和 seconds。
- Doppler 单位：Hz。
- 矩阵方向：行对应 Doppler，列对应 delay。
- 关系说明：zero-Doppler cut 与自匹配滤波输出在相同 delay 排列下等价。

### zero-Doppler cut

- 指标含义：`fd = 0` 的距离延迟切片。
- 用途：可用于与自相关脉压结果交叉验证。
- 输出：`delay_samples` 和对应的归一化幅度。

### zero-delay Doppler cut

- 指标含义：`delay = 0` 的 Doppler 响应切片。
- 用途：用于计算多普勒容忍性。
- 输出：`doppler_hz` 和对应的归一化幅度。

### 多普勒容忍性

- 指标名称：`doppler_tolerance_hz`。
- 定义：给定 `loss_db`，找到 zero-delay Doppler cut 相对 `fd = 0` 响应下降到 `10^(-loss_db / 20)` 的正负 Doppler crossing，取 `min(abs(negative_crossing), abs(positive_crossing))`。
- 单位：Hz。
- 指标方向：越大越好。
- 适用条件：Doppler 网格必须覆盖正负 crossing，且网格分辨率足以支持线性插值定位。
- 不可用条件：如果网格无法覆盖 crossing，则抛出异常，不返回猜测值或网格边界。

## 探测性能模型

### 模型假设

本步只实现单脉冲匹配滤波平方律检测。观测信号为 `x = alpha * s + n`，其中 `s` 是已知复基带目标回波信号向量，`alpha` 是非起伏目标复幅度且目标相位未知，`n ~ CN(0, sigma^2 I)` 是复高斯白噪声。`sigma^2` 表示每个复采样点的噪声功率，即 `E[|n[k]|^2]`。

匹配滤波输出为 `y = sum_k x[k] * conj(s[k])`。信号能量为 `Es = sum_k |s[k]|^2`。归一化检测统计量为 `T = |y|^2 / (sigma^2 * Es)`。

### 检测门限

- 指标名称：`detection_threshold_normalized`。
- 公式：`eta = -ln(Pfa)`。
- 单位：无量纲。
- 适用条件：`0 < Pfa < 1`。

### 虚警概率

- 指标名称：`pfa`。
- 公式：`Pfa = exp(-eta)`。
- 说明：在 H0 下，`T ~ Exp(1)`。

### 输出 SNR

- 指标名称：`output_snr_linear` / `output_snr_db`。
- 公式：`gamma = Es / sigma^2`。
- 说明：`Es = sum(|s[k]|^2)`，`sigma^2 = E[|n[k]|^2]`。
- 单位：线性值或 dB。

### 检测概率

- 指标名称：`pd`。
- 公式：`Pd = scipy.stats.ncx2.sf(2 * eta, df=2, nc=2 * gamma)`。
- 说明：在 H1 下，`2T ~ chi2(df=2, nc=2 * gamma)`。该公式只适用于本模块定义的复高斯白噪声、已知波形、单目标、非起伏幅度、未知相位、匹配滤波平方律检测模型。

### 所需输出 SNR

- 指标名称：`required_output_snr_linear` / `required_output_snr_db`。
- 定义：通过数值反解 `Pd = target_pd` 得到。
- 说明：如果 `target_pd <= pfa`，所需输出 SNR 为 0；如果给定搜索范围无法达到 `target_pd`，则抛出异常，不返回猜测值。

### 匹配滤波处理增益

- 指标名称：`matched_filter_processing_gain_db`。
- 定义：`output_snr / average_sample_snr`。
- 当前约定：`average_sample_snr = mean(|s|^2) / sigma^2`，因此长度为 `N` 的完整信号向量对应处理增益 `10 * log10(N)`。

## 宽带复高斯噪声压制干扰模型

### 模型假设

本步只实现 complex AWGN barrage jamming。目标信号为 `s[k]`，热噪声为 `n[k] ~ CN(0, sigma_n^2)`，宽带噪声压制干扰为 `j[k] ~ CN(0, sigma_j^2)`，观测信号为 `x[k] = s[k] + n[k] + j[k]`。

本模型假设 `j[k]` 与 `n[k]` 独立，且二者在时间采样上均为白噪声；目标为非起伏确定目标；检测器沿用单脉冲匹配滤波平方律检测模型。干扰被视为额外高斯噪声，因此总扰动方差为 `sigma_total^2 = sigma_n^2 + sigma_j^2`。

该模型不代表窄带干扰、欺骗干扰或复杂电磁环境。

### JSR

- 指标名称：`jsr_linear` / `jsr_db`。
- 公式：`JSR = sigma_j^2 / mean(|s[k]|^2)`。
- 单位：线性值或 dB。
- 说明：本项目中 JSR 是干扰方差与目标平均采样功率之比，不是发射端功率比或频谱密度比。

### 干扰下输出 SINR

- 指标名称：`jammed_output_sinr_linear` / `jammed_output_sinr_db`。
- 公式：`gamma_jam = Es / (sigma_n^2 + sigma_j^2)`。
- 说明：`Es = sum(|s[k]|^2)`。
- 单位：线性值或 dB。

### 干扰下检测概率

- 指标名称：`jammed_pd`。
- 说明：使用单脉冲匹配滤波平方律检测模型，以 `gamma_jam` 替代无干扰输出 SNR。

### 检测概率保持率

- 指标名称：`pd_retention`。
- 公式：`pd_retention = jammed_pd / clean_pd`。
- 适用条件：`clean_pd > 0`，且干扰下检测概率不应超过无干扰检测概率。

### 抗干扰裕度

- 指标名称：`jamming_margin_jsr_linear` / `jamming_margin_jsr_db`。
- 定义：在给定 `target_pd` 和 `pfa` 下，满足 `Pd_jam >= target_pd` 的最大可承受 JSR。
- 不可用条件：如果无干扰条件下 `clean_pd` 无法满足 `target_pd`，则抗干扰裕度不可定义并抛出异常，不返回猜测值。

## 反侦察 / 低截获波形暴露特征

### 模块定位

本模块只计算可由波形本身严格得到的暴露特征，不输出 `intercept_probability`、
`intercept_range_ratio` 或侦收机检测性能。截获概率依赖侦收机灵敏度、侦收机接收带宽、
侦收机天线增益、侦收距离、传播损耗、积分时间、检测门限、扫描方式以及是否具备波形先验。
这些模型未定义前，不允许返回截获概率或猜测值。

### 峰值功率

- 指标名称：`peak_power_w`。
- 定义：`peak_power_w = max(|s[k]|^2)`。
- 单位：W，前提是 IQ 幅度按 `sqrt(W)` 标定。
- 指标方向：从低截获角度通常越低越好。
- 适用条件：输入必须是一维、非空、非全零复基带信号。

### 平均功率

- 指标名称：`average_power_w`。
- 定义：`average_power_w = mean(|s[k]|^2)`。
- 单位：W，前提是 IQ 幅度按 `sqrt(W)` 标定。
- 指标方向：从能量暴露角度通常越低越好。
- 适用条件：输入必须是一维、非空、非全零复基带信号。

### PAPR

- 指标名称：`papr_db`。
- 定义：`PAPR = peak_power_w / average_power_w`，`papr_db = 10 * log10(PAPR)`。
- 单位：dB。
- 说明：该指标也属于工程实现性指标，在反侦察分析中可作为峰值暴露特征的辅助指标。
- 不可用条件：零功率信号不可计算 PAPR。

### 名义平均功率谱密度

- 指标名称：`nominal_avg_psd_w_per_hz`。
- 定义：`nominal_avg_psd_w_per_hz = average_power_w / bandwidth_hz`。
- 单位：W/Hz。
- 说明：这不是真实 PSD 估计；该指标假设平均功率在指定带宽内均匀分布，必须使用
  `nominal` 命名。
- 不可用条件：`bandwidth_hz <= 0` 或 `average_power_w < 0`。

### 双边 periodogram PSD

- 指标名称：`psd_w_per_hz`。
- 定义：使用复基带 IQ 计算双边 periodogram。
- 计算方式：`scipy.signal.periodogram`，参数固定为 `window="boxcar"`、`detrend=False`、
  `return_onesided=False`、`scaling="density"`。
- 频率排列：对输出频率和 PSD 使用 `fftshift`，使频率从负到正排列。
- 单位：W/Hz，前提是 IQ 幅度按 `sqrt(W)` 标定。
- 一致性检查：PSD 对频率积分应近似等于时域 `average_power_w`；若不满足数值容差，
  则抛出异常。
- 适用条件：当前实现固定使用 `boxcar` 窗；后续如支持其他窗函数，必须明确功率修正方式。

### 占用带宽

- 指标名称：`occupied_bandwidth_hz`。
- 定义：基于 PSD 累计功率计算 central occupied bandwidth。
- 参数：`occupied_power_fraction`，默认 `0.99`。
- 计算方式：低端累计功率比例为 `(1 - occupied_power_fraction) / 2`，高端累计功率比例为
  `1 - (1 - occupied_power_fraction) / 2`，使用频率 bin 边界计算下边界和上边界。
- 单位：Hz。
- 指标方向：视任务而定；从低截获角度，较宽带宽有助于降低单位带宽能量，但也增加频谱占用。
- 不可用条件：频率网格非单调、非等间隔、总谱功率非正或 `occupied_power_fraction` 不在
  `(0, 1)` 内。

### 时宽带宽积

- 指标名称：`tbp`。
- 定义：`tbp = bandwidth_hz * pulse_width_s`。
- 单位：无量纲。
- 说明：大 TBP 有利于雷达自身匹配处理，同时配合低峰值功率和宽带扩展形成低截获特征。
- 不可用条件：`bandwidth_hz <= 0` 或 `pulse_width_s <= 0`。

### 占空比

- 指标名称：`duty_cycle`。
- 定义：`duty_cycle = pulse_width_s * prf_hz`，或者 `duty_cycle = pulse_width_s / pri_s`。
- 单位：无量纲。
- 适用条件：`prf_hz` 和 `pri_s` 至少提供一个；如果二者都提供，必须满足
  `prf_hz ~= 1 / pri_s`。
- 不可用条件：未提供 PRF/PRI 时不计算该指标；如果 `duty_cycle > 1`，则抛出异常。

## 分辨能力指标

### 距离分辨率

- 指标名称：`range_resolution_m`。
- 公式：`range_resolution_m = c / (2 * bandwidth_hz)`。
- 单位：m。
- 指标方向：通常越小越好。
- 适用条件：`bandwidth_hz > 0`。

### 距离采样间隔

- 指标名称：`range_sample_spacing_m`。
- 公式：`range_sample_spacing_m = c / (2 * sample_rate_hz)`。
- 单位：m。
- 指标方向：通常越小越好，但不等同于物理距离分辨率。
- 适用条件：`sample_rate_hz > 0`。

### 波长

- 指标名称：`wavelength_m`。
- 公式：`wavelength_m = c / carrier_frequency_hz`。
- 单位：m。
- 适用条件：`carrier_frequency_hz > 0`。
- 不可用条件：缺少载频时不计算波长，也不推测速度分辨率。

### 相干处理时间

- 指标名称：`cpi_s`。
- 支持定义：直接输入 `cpi_s`，或由 `num_pulses + prf_hz`、`num_pulses + pri_s` 推导。
- 一致性要求：如果 `prf_hz` 和 `pri_s` 同时给出，必须满足 `prf_hz ~= 1 / pri_s`；
  如果直接 `cpi_s` 和脉冲参数推导值同时给出，二者必须一致。
- 不允许：不把 `pulse_width_s` 自动当作 CPI。
- 不可用条件：缺少上述 CPI 定义参数时，CPI、多普勒分辨率和速度分辨率标记为不可用。

### 多普勒分辨率

- 指标名称：`doppler_resolution_hz`。
- 公式：`doppler_resolution_hz = 1 / cpi_s`。
- 单位：Hz。
- 指标方向：通常越小越好。
- 不可用条件：缺少严格定义的 CPI。

### 速度分辨率

- 指标名称：`velocity_resolution_mps`。
- 公式：`velocity_resolution_mps = wavelength_m / (2 * cpi_s)`。
- 单位：m/s。
- 指标方向：通常越小越好。
- 不可用条件：缺少载频或 CPI 时不计算，不返回猜测值。

## 评分规则

评分模块只根据 `ScoringConfig` 中显式配置的归一化边界、方向和权重计算百分制得分。
默认 `configs/scoring_default.json` 只是演示配置，不代表绝对物理评价标准。

- `higher_better`：`min_value` 对应 0 分，`max_value` 对应 100 分，中间线性插值。
- `lower_better`：`min_value` 对应 100 分，`max_value` 对应 0 分，中间线性插值。
- `target_range`：`target_min <= value <= target_max` 得 100 分，目标区间外按
  `min_value/target_min` 与 `target_max/max_value` 两侧线性下降。
- 维度得分：每个 axis 根据可用指标的权重计算加权平均。
- 总分：根据可用 axis 的权重计算加权平均。
- 不可用指标：如果模型参数缺失或严格定义不满足，指标标记为 unavailable 并记录 reason；
  不把 unavailable 指标按 0 分处理。
- 不可用维度：如果某个 axis 没有任何可用指标，该 axis 标记为 unavailable，不给伪造分数。

## 本阶段不计算的内容

- 本步不计算距离-多普勒耦合指标。
- 暂不实现 Swerling I/II/III/IV 目标起伏模型。
- 暂不实现 CFAR。
- 暂不实现杂波模型。
- 暂不实现多脉冲非相干或相干积累。
- 暂不实现检测曲线 Monte Carlo 仿真。
- 暂不实现窄带瞄准干扰。
- 暂不实现扫频干扰。
- 暂不实现距离欺骗干扰。
- 暂不实现速度欺骗干扰。
- 暂不实现干扰类型识别。
- 暂不实现干扰抑制算法。
- 暂不将本模型结果泛化为所有抗干扰场景。
- 暂不实现 `intercept_probability`。
- 暂不实现 `intercept_range_ratio`。
- 暂不实现 `receiver_detection_threshold`。
- 暂不实现 `receiver_required_snr`。
- 暂不实现 `waveform_classification_probability`。
- 暂不实现 `parameter_estimation_error_for_intercept_receiver`。
- 这些指标后续需要严格定义模型假设、评价范围或统计检验方式。

## 适用条件

- 当前信号均按复基带 IQ 表达。
- 功率类指标直接基于离散 IQ 样本计算。
- 当 IQ 幅度按 `sqrt(W)` 标定时，`abs(iq)^2` 可解释为 W。
- `phase_code` 要求总采样点数为整数，且总采样点数必须能被码长整除。
- 零多普勒旁瓣指标基于自匹配滤波输出，不包含非零多普勒切片。

## 结果表达

每个指标使用 `MetricValue` 表达，包含指标名称、数值、单位和说明。每个评估维度使用 `AxisScore` 表达，包含维度名称、得分和指标列表。完整评估使用 `EvaluationResult` 表达。

## 约束

- 指标计算必须在 `radar_eval_core` 中实现。
- UI 层只展示和组织结构化结果。
- 大语言模型只能解释结构化指标结果，不允许直接计算雷达指标。
