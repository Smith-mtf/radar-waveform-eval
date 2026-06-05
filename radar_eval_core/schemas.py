"""雷达波形性能评估的数据结构定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field


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
