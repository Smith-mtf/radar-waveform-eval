"""单脉冲匹配滤波平方律检测模型。"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
from scipy import optimize, stats

from .schemas import DetectionMetrics


class DetectionModelError(ValueError):
    """检测模型输入不满足当前统计假设或数值求解要求。"""


def db_to_linear(value_db: float) -> float:
    """将 dB 值转换为线性值。"""
    if not math.isfinite(value_db):
        raise DetectionModelError("value_db 必须是有限数值。")
    return float(10.0 ** (value_db / 10.0))


def linear_to_db(value_linear: float) -> float:
    """将正线性值转换为 dB。"""
    if not math.isfinite(value_linear) or value_linear <= 0:
        raise DetectionModelError("value_linear 必须是有限正数。")
    return float(10.0 * math.log10(value_linear))


def validate_probability(value: float, name: str) -> float:
    """校验概率满足 0 < value < 1。"""
    if not math.isfinite(value) or not 0.0 < value < 1.0:
        raise DetectionModelError(f"{name} 必须满足 0 < {name} < 1。")
    return float(value)


def validate_signal_for_detection(signal: npt.ArrayLike) -> npt.NDArray[np.complex128]:
    """校验目标信号为一维、非空、非全零的 complex128 数组。"""
    try:
        array = np.asarray(signal, dtype=np.complex128)
    except (TypeError, ValueError) as exc:
        raise DetectionModelError("signal 必须能转换为 complex128 数组。") from exc

    if array.ndim != 1:
        raise DetectionModelError("signal 必须是一维数组。")
    if array.size == 0:
        raise DetectionModelError("signal 不能为空。")
    if not np.all(np.isfinite(array)):
        raise DetectionModelError("signal 必须只包含有限数值。")
    if not np.any(array):
        raise DetectionModelError("signal 不能全零。")
    return array


def compute_signal_energy(signal: npt.ArrayLike) -> float:
    """计算信号能量 Es = sum(abs(signal) ** 2)。"""
    target_signal = validate_signal_for_detection(signal)
    signal_energy = float(np.sum(np.abs(target_signal) ** 2))
    if not math.isfinite(signal_energy) or signal_energy <= 0:
        raise DetectionModelError("signal_energy 必须是有限正数。")
    return signal_energy


def compute_average_sample_snr_linear(
    target_signal: npt.ArrayLike,
    noise_variance: float,
) -> float:
    """计算平均采样 SNR，定义为 mean(abs(target_signal) ** 2) / noise_variance。"""
    _validate_noise_variance(noise_variance)
    signal = validate_signal_for_detection(target_signal)
    return float(np.mean(np.abs(signal) ** 2) / noise_variance)


def compute_matched_filter_output_snr_linear(
    target_signal: npt.ArrayLike,
    noise_variance: float,
) -> float:
    """计算匹配滤波输出 SNR，定义为 Es / noise_variance。"""
    _validate_noise_variance(noise_variance)
    return float(compute_signal_energy(target_signal) / noise_variance)


def compute_matched_filter_processing_gain_db(target_signal: npt.ArrayLike) -> float:
    """计算相对平均采样 SNR 定义的匹配滤波处理增益。"""
    signal = validate_signal_for_detection(target_signal)
    signal_energy = compute_signal_energy(signal)
    average_sample_power = float(np.mean(np.abs(signal) ** 2))
    if average_sample_power <= 0:
        raise DetectionModelError("average_sample_power 必须大于 0。")

    processing_gain_linear = signal_energy / average_sample_power
    return linear_to_db(processing_gain_linear)


def compute_detection_threshold_from_pfa(pfa: float) -> float:
    """由虚警概率计算归一化门限 eta = -ln(Pfa)。"""
    validated_pfa = validate_probability(pfa, "pfa")
    return float(-math.log(validated_pfa))


def compute_pfa_from_threshold(threshold: float) -> float:
    """由归一化门限计算虚警概率 Pfa = exp(-eta)。"""
    if not math.isfinite(threshold) or threshold < 0:
        raise DetectionModelError("threshold 必须是有限非负数。")
    return float(math.exp(-threshold))


def compute_pd_square_law(output_snr_linear: float, pfa: float) -> float:
    """计算当前匹配滤波平方律检测模型下的 Pd，不适用于所有雷达检测场景。"""
    if not math.isfinite(output_snr_linear) or output_snr_linear < 0:
        raise DetectionModelError("output_snr_linear 必须是有限非负数。")

    threshold = compute_detection_threshold_from_pfa(pfa)
    pd = float(stats.ncx2.sf(2.0 * threshold, df=2, nc=2.0 * output_snr_linear))
    if not math.isfinite(pd):
        raise DetectionModelError("Pd 计算结果不是有限数值。")
    return min(1.0, max(0.0, pd))


def compute_required_output_snr_linear(
    target_pd: float,
    pfa: float,
    *,
    tolerance: float = 1e-8,
    max_snr_linear: float = 1e8,
) -> float:
    """反解达到 target_pd 和 pfa 所需的最小匹配滤波输出 SNR。"""
    validated_target_pd = validate_probability(target_pd, "target_pd")
    validated_pfa = validate_probability(pfa, "pfa")
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise DetectionModelError("tolerance 必须是有限正数。")
    if not math.isfinite(max_snr_linear) or max_snr_linear <= 0:
        raise DetectionModelError("max_snr_linear 必须是有限正数。")

    if validated_target_pd <= validated_pfa:
        return 0.0

    def objective(output_snr_linear: float) -> float:
        return compute_pd_square_law(output_snr_linear, validated_pfa) - validated_target_pd

    if objective(max_snr_linear) < 0:
        raise DetectionModelError("在 max_snr_linear 范围内无法达到 target_pd。")

    return float(optimize.brentq(objective, 0.0, max_snr_linear, xtol=tolerance))


def compute_required_output_snr_db(target_pd: float, pfa: float) -> float:
    """反解达到 target_pd 和 pfa 所需的输出 SNR，单位 dB。"""
    required_snr_linear = compute_required_output_snr_linear(target_pd, pfa)
    if required_snr_linear == 0:
        return -math.inf
    return linear_to_db(required_snr_linear)


def compute_detection_metrics(
    target_signal: npt.ArrayLike,
    noise_variance: float,
    pfa: float,
    target_pd: float | None = None,
) -> DetectionMetrics:
    """汇总当前统计检测模型下的门限、SNR、Pd 和可选 required SNR。"""
    _validate_noise_variance(noise_variance)
    signal = validate_signal_for_detection(target_signal)
    threshold_normalized = compute_detection_threshold_from_pfa(pfa)
    signal_energy = compute_signal_energy(signal)
    average_sample_snr_linear = compute_average_sample_snr_linear(signal, noise_variance)
    output_snr_linear = compute_matched_filter_output_snr_linear(signal, noise_variance)
    pd = compute_pd_square_law(output_snr_linear, pfa)

    required_output_snr_linear: float | None = None
    required_output_snr_db: float | None = None
    if target_pd is not None:
        required_output_snr_linear = compute_required_output_snr_linear(target_pd, pfa)
        required_output_snr_db = (
            -math.inf
            if required_output_snr_linear == 0
            else linear_to_db(required_output_snr_linear)
        )

    return DetectionMetrics(
        pfa=validate_probability(pfa, "pfa"),
        threshold_normalized=threshold_normalized,
        signal_energy=signal_energy,
        noise_variance=float(noise_variance),
        average_sample_snr_linear=average_sample_snr_linear,
        average_sample_snr_db=linear_to_db(average_sample_snr_linear),
        output_snr_linear=output_snr_linear,
        output_snr_db=linear_to_db(output_snr_linear),
        matched_filter_processing_gain_db=compute_matched_filter_processing_gain_db(signal),
        pd=pd,
        target_pd=None if target_pd is None else validate_probability(target_pd, "target_pd"),
        required_output_snr_linear=required_output_snr_linear,
        required_output_snr_db=required_output_snr_db,
    )


def estimate_detection_metrics() -> None:
    """保留旧占位入口；请直接调用 compute_detection_metrics。"""
    raise NotImplementedError("请使用 compute_detection_metrics。")


def _validate_noise_variance(noise_variance: float) -> None:
    """校验复采样点噪声功率为有限正数。"""
    if not math.isfinite(noise_variance) or noise_variance <= 0:
        raise DetectionModelError("noise_variance 必须是有限正数。")
