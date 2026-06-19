"""雷达波形性能评估的数据结构定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Self

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field, model_validator

WaveformType = Literal["rect", "lfm", "phase_code"]


def derive_nominal_bandwidth_hz(
    waveform_type: WaveformType,
    pulse_width_s: float,
    phase_code: list[int] | None = None,
    explicit_bandwidth_hz: float | None = None,
) -> float:
    """按波形类型返回用于指标计算的名义带宽。

    对 `phase_code`，`pulse_width_s` 表示单个子脉冲/码片宽度，因此名义带宽按
    码片率 `1 / pulse_width_s` 派生。
    """
    if pulse_width_s <= 0:
        raise ValueError("pulse_width_s 必须大于 0。")

    if waveform_type == "lfm":
        if explicit_bandwidth_hz is None or explicit_bandwidth_hz <= 0:
            raise ValueError("lfm 波形必须提供大于 0 的 bandwidth_hz。")
        return float(explicit_bandwidth_hz)

    if waveform_type == "rect":
        return float(1.0 / pulse_width_s)

    if waveform_type == "phase_code":
        code = phase_code
        _validate_binary_phase_code(code)
        return float(1.0 / pulse_width_s)

    raise ValueError(f"不支持的波形类型: {waveform_type}")


def derive_total_pulse_width_s(
    waveform_type: WaveformType,
    pulse_width_s: float,
    phase_code: list[int] | None = None,
) -> float:
    """返回波形完整脉冲时宽。

    `rect` 和 `lfm` 直接使用配置的 `pulse_width_s`；`phase_code` 将
    `pulse_width_s` 解释为子脉冲/码片宽度，并乘以码长得到完整编码脉冲时宽。
    """
    if pulse_width_s <= 0:
        raise ValueError("pulse_width_s 必须大于 0。")

    if waveform_type in {"rect", "lfm"}:
        return float(pulse_width_s)

    if waveform_type == "phase_code":
        code = phase_code
        _validate_binary_phase_code(code)
        assert code is not None
        return float(len(code) * pulse_width_s)

    raise ValueError(f"不支持的波形类型: {waveform_type}")


def _validate_binary_phase_code(phase_code: list[int] | None) -> None:
    """校验二相相位码为完整的 0/1 或 -1/1 序列。"""
    if phase_code is None:
        raise ValueError("phase_code 波形必须提供相位编码序列。")
    if len(phase_code) < 2:
        raise ValueError("phase_code 长度必须至少为 2。")

    unique_values = set(phase_code)
    if unique_values not in ({0, 1}, {-1, 1}):
        raise ValueError("phase_code 只允许使用完整的 0/1 或 -1/1 二相编码。")


@dataclass(slots=True)
class WaveformSignal:
    """生成后的复基带波形信号。"""

    t: npt.NDArray[np.float64]
    iq: npt.NDArray[np.complex128]
    sample_rate_hz: float
    metadata: dict[str, Any] = field(default_factory=dict)


class WaveformConfig(BaseModel):
    """波形基础配置。"""

    waveform_type: WaveformType = Field(
        default="lfm",
        description="波形类型",
    )
    name: str = Field(default="default_waveform", description="波形名称")
    carrier_frequency_hz: float = Field(default=10e9, gt=0, description="载频")
    bandwidth_hz: float = Field(default=10e6, gt=0, description="带宽")
    pulse_width_s: float = Field(
        default=10e-6,
        gt=0,
        description="rect/lfm 为脉宽；phase_code 为子脉冲宽度",
    )
    sample_rate_hz: float = Field(default=50e6, gt=0, description="采样率")
    peak_power_w: float = Field(default=1000.0, gt=0, description="峰值功率")
    phase_code: list[int] | None = Field(default=None, description="二相相位编码序列")

    @model_validator(mode="after")
    def validate_phase_code_usage(self) -> Self:
        """校验相位编码配置与波形类型一致。"""
        if self.waveform_type != "phase_code":
            if self.phase_code is not None:
                raise ValueError("phase_code 仅允许用于 phase_code 波形。")
            self.bandwidth_hz = derive_nominal_bandwidth_hz(
                self.waveform_type,
                self.pulse_width_s,
                explicit_bandwidth_hz=self.bandwidth_hz,
            )
            return self

        self.bandwidth_hz = derive_nominal_bandwidth_hz(
            self.waveform_type,
            self.pulse_width_s,
            phase_code=self.phase_code,
            explicit_bandwidth_hz=self.bandwidth_hz,
        )

        return self


class MainlobeSpec(BaseModel):
    """零多普勒旁瓣指标的主瓣边界定义。"""

    method: Literal["manual_guard_samples", "first_local_minimum", "null_to_null"]
    guard_samples: int | None = Field(default=None, ge=0, description="主峰左右保护采样点数")
    null_tolerance: float = Field(default=1e-6, gt=0, description="零点检测相对门限")

    @model_validator(mode="after")
    def validate_manual_guard_samples(self) -> Self:
        """校验手动主瓣保护区参数。"""
        if self.method == "manual_guard_samples" and self.guard_samples is None:
            raise ValueError("manual_guard_samples 方法必须提供 guard_samples。")
        return self


class ZeroDopplerSidelobeMetrics(BaseModel):
    """零多普勒自相关旁瓣指标。"""

    peak_index: int = Field(ge=0, description="主峰索引")
    peak_magnitude: float = Field(gt=0, description="主峰幅度")
    mainlobe_left_index: int = Field(ge=0, description="主瓣左边界索引")
    mainlobe_right_index: int = Field(ge=0, description="主瓣右边界索引")
    mainlobe_width_samples: int = Field(ge=1, description="主瓣宽度，单位为 samples")
    zero_doppler_pslr_db: float = Field(description="零多普勒峰值旁瓣比，单位为 dB")
    zero_doppler_islr_db: float = Field(description="零多普勒积分旁瓣比，单位为 dB")

    @model_validator(mode="after")
    def validate_mainlobe_bounds(self) -> Self:
        """校验主瓣边界与宽度一致。"""
        if not self.mainlobe_left_index <= self.peak_index <= self.mainlobe_right_index:
            raise ValueError("主瓣边界必须包含 peak_index。")
        expected_width = self.mainlobe_right_index - self.mainlobe_left_index + 1
        if self.mainlobe_width_samples != expected_width:
            raise ValueError("mainlobe_width_samples 与主瓣边界不一致。")
        return self


@dataclass(slots=True)
class AmbiguityFunctionResult:
    """离散非周期二维模糊函数计算结果。"""

    delay_samples: npt.NDArray[np.int_]
    delay_seconds: npt.NDArray[np.float64]
    doppler_hz: npt.NDArray[np.float64]
    ambiguity_complex: npt.NDArray[np.complex128]
    ambiguity_magnitude: npt.NDArray[np.float64]
    ambiguity_magnitude_normalized: npt.NDArray[np.float64]
    peak_magnitude: float
    peak_delay_samples: int
    peak_doppler_hz: float
    sample_rate_hz: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DopplerToleranceMetrics:
    """基于 zero-delay Doppler cut 的多普勒容忍性指标。"""

    loss_db: float
    threshold_linear: float
    negative_crossing_hz: float
    positive_crossing_hz: float
    doppler_tolerance_hz: float
    zero_delay_peak_magnitude: float


@dataclass(slots=True)
class SpectrumEstimate:
    """双边 periodogram PSD 估计结果。"""

    frequency_hz: npt.NDArray[np.float64]
    psd_w_per_hz: npt.NDArray[np.float64]
    frequency_resolution_hz: float
    total_power_from_psd_w: float
    average_power_time_domain_w: float
    relative_power_error: float
    method: str
    window: str
    scaling: str
    return_onesided: bool


class ResolutionMetrics(BaseModel):
    """严格定义的距离、多普勒和速度分辨能力指标。"""

    range_resolution_m: float = Field(gt=0, description="距离分辨率")
    range_sample_spacing_m: float = Field(gt=0, description="距离采样间隔")
    wavelength_m: float | None = Field(default=None, gt=0, description="波长")
    cpi_s: float | None = Field(default=None, gt=0, description="相干处理时间")
    doppler_resolution_hz: float | None = Field(default=None, gt=0, description="多普勒分辨率")
    velocity_resolution_mps: float | None = Field(default=None, gt=0, description="速度分辨率")


class DetectionMetrics(BaseModel):
    """单脉冲匹配滤波平方律检测模型的结构化指标。"""

    model_name: str = Field(default="single_pulse_matched_filter_square_law_cawg")
    noise_model: str = Field(default="complex_awgn")
    target_model: str = Field(default="deterministic_nonfluctuating_unknown_phase")
    detector: str = Field(default="matched_filter_square_law")
    pfa: float = Field(gt=0, lt=1, description="虚警概率")
    threshold_normalized: float = Field(ge=0, description="归一化检测门限")
    signal_energy: float = Field(gt=0, description="信号能量")
    noise_variance: float = Field(gt=0, description="每个复采样点的噪声功率")
    average_sample_snr_linear: float = Field(gt=0, description="平均采样 SNR 线性值")
    average_sample_snr_db: float = Field(description="平均采样 SNR，单位 dB")
    output_snr_linear: float = Field(gt=0, description="匹配滤波输出 SNR 线性值")
    output_snr_db: float = Field(description="匹配滤波输出 SNR，单位 dB")
    matched_filter_processing_gain_db: float = Field(description="匹配滤波处理增益，单位 dB")
    pd: float = Field(ge=0, le=1, description="检测概率")
    target_pd: float | None = Field(default=None, description="目标检测概率")
    required_output_snr_linear: float | None = Field(
        default=None,
        description="目标 Pd 所需输出 SNR",
    )
    required_output_snr_db: float | None = Field(
        default=None,
        description="目标 Pd 所需输出 SNR，单位 dB",
    )


class JammingMetrics(BaseModel):
    """宽带复高斯噪声压制干扰模型的结构化指标。"""

    model_name: str = Field(default="wideband_complex_gaussian_noise_jamming")
    jammer_model: str = Field(default="complex_awgn_barrage")
    detector_model: str = Field(default="single_pulse_matched_filter_square_law_cawg")
    pfa: float = Field(gt=0, lt=1, description="虚警概率")
    jsr_linear: float = Field(ge=0, description="干信比线性值")
    jsr_db: float = Field(description="干信比，单位 dB")
    signal_energy: float = Field(gt=0, description="信号能量")
    average_target_sample_power: float = Field(gt=0, description="目标平均采样功率")
    noise_variance: float = Field(gt=0, description="热噪声方差")
    jammer_variance: float = Field(ge=0, description="干扰方差")
    total_disturbance_variance: float = Field(gt=0, description="总扰动方差")
    clean_output_snr_linear: float = Field(gt=0, description="无干扰输出 SNR 线性值")
    clean_output_snr_db: float = Field(description="无干扰输出 SNR，单位 dB")
    jammed_output_sinr_linear: float = Field(gt=0, description="干扰下输出 SINR 线性值")
    jammed_output_sinr_db: float = Field(description="干扰下输出 SINR，单位 dB")
    clean_pd: float = Field(ge=0, le=1, description="无干扰检测概率")
    jammed_pd: float = Field(ge=0, le=1, description="干扰下检测概率")
    pd_retention: float = Field(ge=0, le=1, description="检测概率保持率")
    target_pd: float | None = Field(default=None, description="目标检测概率")
    jamming_margin_jsr_linear: float | None = Field(default=None, description="抗干扰裕度 JSR")
    jamming_margin_jsr_db: float | None = Field(default=None, description="抗干扰裕度 JSR，单位 dB")


class LpiExposureMetrics(BaseModel):
    """仅由波形本身计算的低截获暴露特征。"""

    model_name: str = Field(default="waveform_lpi_exposure_features")
    feature_scope: str = Field(default="waveform_features_only_no_intercept_receiver_model")
    peak_power_w: float = Field(gt=0, description="峰值功率")
    average_power_w: float = Field(gt=0, description="平均功率")
    papr_db: float = Field(ge=0, description="峰均功率比，单位 dB")
    bandwidth_hz: float = Field(gt=0, description="名义带宽")
    pulse_width_s: float = Field(gt=0, description="完整脉冲时宽")
    nominal_avg_psd_w_per_hz: float = Field(ge=0, description="名义平均功率谱密度")
    tbp: float = Field(gt=0, description="时宽带宽积")
    psd_total_power_w: float = Field(gt=0, description="PSD 积分得到的总功率")
    psd_relative_power_error: float = Field(ge=0, description="PSD 积分功率相对误差")
    duty_cycle: float | None = Field(default=None, gt=0, le=1, description="占空比")
    duty_cycle_definition: str | None = Field(default=None, description="占空比计算定义")


class ScenarioConfig(BaseModel):
    """评估场景基础配置。"""

    name: str = Field(default="default_scenario", description="场景名称")
    target_range_m: float = Field(default=50_000.0, gt=0, description="目标距离")
    target_radial_velocity_mps: float = Field(default=100.0, description="目标径向速度")
    signal_to_noise_ratio_db: float = Field(default=10.0, description="输入信噪比")


class JammerConfig(BaseModel):
    """干扰机基础配置。"""

    enabled: bool = Field(default=False, description="是否启用干扰")
    jammer_type: Literal["none", "noise", "sweep", "deception"] = Field(
        default="none",
        description="干扰类型",
    )
    jammer_to_signal_ratio_db: float = Field(default=0.0, description="干信比")


class EvaluationSettings(BaseModel):
    """算法评估流水线参数。"""

    pfa: float = Field(default=1e-6, gt=0, lt=1, description="虚警概率")
    target_pd: float | None = Field(default=0.9, gt=0, lt=1, description="目标检测概率")
    noise_variance: float = Field(default=1.0, gt=0, description="每个复采样点噪声功率")
    mainlobe_spec: MainlobeSpec = Field(
        default_factory=lambda: MainlobeSpec(method="first_local_minimum"),
        description="零多普勒旁瓣主瓣定义",
    )
    doppler_max_hz: float = Field(default=100_000.0, gt=0, description="对称 Doppler 网格最大频率")
    doppler_points: int = Field(default=1001, ge=3, description="Doppler 网格点数")
    doppler_loss_db: float = Field(default=3.0, gt=0, description="多普勒容忍性损失门限")
    cpi_s: float | None = Field(default=None, gt=0, description="直接给定的 CPI")
    num_pulses: int | None = Field(default=64, ge=1, description="CPI 内脉冲数")
    prf_hz: float | None = Field(default=1000.0, gt=0, description="脉冲重复频率")
    pri_s: float | None = Field(default=None, gt=0, description="脉冲重复间隔")

    @model_validator(mode="after")
    def validate_doppler_grid_shape(self) -> Self:
        """校验默认生成的对称 Doppler 网格包含唯一零频点。"""
        if self.doppler_points % 2 == 0:
            raise ValueError("doppler_points 必须为奇数，才能生成包含 0 的对称 Doppler 网格。")
        return self


class ScenarioEnvironmentConfig(BaseModel):
    """可独立加载的场景与环境配置。"""

    scenario: ScenarioConfig = Field(default_factory=ScenarioConfig)
    jammer: JammerConfig = Field(default_factory=JammerConfig)
    evaluation: EvaluationSettings = Field(default_factory=EvaluationSettings)


class EvaluationRequest(BaseModel):
    """一次评估请求。"""

    waveform: WaveformConfig = Field(default_factory=WaveformConfig)
    scenario: ScenarioConfig = Field(default_factory=ScenarioConfig)
    jammer: JammerConfig = Field(default_factory=JammerConfig)
    evaluation: EvaluationSettings = Field(default_factory=EvaluationSettings)


def apply_scenario_environment_config(
    request: EvaluationRequest,
    scenario_environment: ScenarioEnvironmentConfig,
) -> EvaluationRequest:
    """将独立场景与环境配置合并到现有评估请求，保留原波形配置。"""
    return EvaluationRequest(
        waveform=request.waveform,
        scenario=scenario_environment.scenario,
        jammer=scenario_environment.jammer,
        evaluation=scenario_environment.evaluation,
    )


class MetricAvailability(BaseModel):
    """指标可用性说明。"""

    metric_id: str = Field(description="指标唯一标识")
    available: bool = Field(description="指标是否可用")
    reason: str | None = Field(default=None, description="不可用原因")


class RawMetric(BaseModel):
    """评估流水线输出的原始指标。"""

    metric_id: str = Field(description="指标唯一标识")
    axis_id: str = Field(description="所属评分维度")
    value: float | None = Field(default=None, description="指标数值；不可用时为 None")
    unit: str = Field(default="", description="指标单位")
    available: bool = Field(default=True, description="指标是否可用")
    reason: str | None = Field(default=None, description="不可用原因")
    description: str = Field(default="", description="指标说明")


class MetricValue(BaseModel):
    """单个指标值。"""

    name: str = Field(description="指标名称")
    value: float = Field(description="指标数值")
    unit: str = Field(default="", description="指标单位")
    description: str = Field(default="", description="指标说明")


class AxisScore(BaseModel):
    """一个评估维度的得分。"""

    axis_id: str = Field(default="", description="维度标识")
    name: str = Field(description="维度名称")
    score: float | None = Field(default=None, ge=0, le=100, description="百分制得分")
    available: bool = Field(default=True, description="维度得分是否可用")
    reason: str | None = Field(default=None, description="不可用原因")
    metrics: list[MetricValue] = Field(default_factory=list, description="维度下的指标列表")


class EvaluationResult(BaseModel):
    """一次评估的结构化结果。"""

    request: EvaluationRequest = Field(description="原始评估请求")
    overall_score: float = Field(ge=0, le=100, description="综合得分")
    axis_scores: list[AxisScore] = Field(default_factory=list, description="各维度得分")
    raw_metrics: list[RawMetric] = Field(default_factory=list, description="原始指标列表")
    chart_data: dict[str, Any] = Field(default_factory=dict, description="图表所需轻量数据")
    summary: str = Field(default="", description="结果摘要")
