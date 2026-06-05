"""雷达波形性能评估的数据结构定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Self

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field, model_validator


@dataclass(slots=True)
class WaveformSignal:
    """生成后的复基带波形信号。"""

    t: npt.NDArray[np.float64]
    iq: npt.NDArray[np.complex128]
    sample_rate_hz: float
    metadata: dict[str, Any] = field(default_factory=dict)


class WaveformConfig(BaseModel):
    """波形基础配置。"""

    waveform_type: Literal["rect", "lfm", "phase_code"] = Field(
        default="lfm",
        description="波形类型",
    )
    name: str = Field(default="default_waveform", description="波形名称")
    carrier_frequency_hz: float = Field(default=10e9, gt=0, description="载频")
    bandwidth_hz: float = Field(default=20e6, gt=0, description="带宽")
    pulse_width_s: float = Field(default=20e-6, gt=0, description="脉宽")
    sample_rate_hz: float = Field(default=100e6, gt=0, description="采样率")
    peak_power_w: float = Field(default=1.0, gt=0, description="峰值功率")
    phase_code: list[int] | None = Field(default=None, description="二相相位编码序列")

    @model_validator(mode="after")
    def validate_phase_code_usage(self) -> Self:
        """校验相位编码配置与波形类型一致。"""
        if self.waveform_type != "phase_code":
            if self.phase_code is not None:
                raise ValueError("phase_code 仅允许用于 phase_code 波形。")
            return self

        if self.phase_code is None:
            raise ValueError("phase_code 波形必须提供相位编码序列。")
        if len(self.phase_code) < 2:
            raise ValueError("phase_code 长度必须至少为 2。")

        unique_values = set(self.phase_code)
        if unique_values not in ({0, 1}, {-1, 1}):
            raise ValueError("phase_code 只允许使用完整的 0/1 或 -1/1 二相编码。")

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


class EvaluationRequest(BaseModel):
    """一次评估请求。"""

    waveform: WaveformConfig = Field(default_factory=WaveformConfig)
    scenario: ScenarioConfig = Field(default_factory=ScenarioConfig)
    jammer: JammerConfig = Field(default_factory=JammerConfig)


class MetricValue(BaseModel):
    """单个指标值。"""

    name: str = Field(description="指标名称")
    value: float = Field(description="指标数值")
    unit: str = Field(default="", description="指标单位")
    description: str = Field(default="", description="指标说明")


class AxisScore(BaseModel):
    """一个评估维度的得分。"""

    name: str = Field(description="维度名称")
    score: float = Field(ge=0, le=100, description="百分制得分")
    metrics: list[MetricValue] = Field(default_factory=list, description="维度下的指标列表")


class EvaluationResult(BaseModel):
    """一次评估的结构化结果。"""

    request: EvaluationRequest = Field(description="原始评估请求")
    overall_score: float = Field(ge=0, le=100, description="综合得分")
    axis_scores: list[AxisScore] = Field(default_factory=list, description="各维度得分")
    summary: str = Field(default="", description="结果摘要")
