"""宽带复高斯噪声压制干扰模型。"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from .detection import (
    DetectionModelError,
    compute_matched_filter_output_snr_linear,
    compute_pd_square_law,
    compute_required_output_snr_linear,
    compute_signal_energy,
    validate_probability,
)
from .detection import db_to_linear as _detection_db_to_linear
from .detection import linear_to_db as _detection_linear_to_db
from .schemas import JammingMetrics

_PD_TOLERANCE = 1e-12
_VARIANCE_TOLERANCE = 1e-12


class JammingModelError(ValueError):
    """抗干扰模型输入错误或指标不可定义。"""


def db_to_linear(value_db: float) -> float:
    """将 dB 值转换为线性值。"""
    try:
        return _detection_db_to_linear(value_db)
    except DetectionModelError as exc:
        raise JammingModelError(str(exc)) from exc


def linear_to_db(value_linear: float) -> float:
    """将正线性值转换为 dB。"""
    try:
        return _detection_linear_to_db(value_linear)
    except DetectionModelError as exc:
        raise JammingModelError(str(exc)) from exc


def validate_signal_for_jamming(signal: npt.ArrayLike) -> npt.NDArray[np.complex128]:
    """校验目标信号为一维、非空、非全零的 complex128 数组。"""
    try:
        array = np.asarray(signal, dtype=np.complex128)
    except (TypeError, ValueError) as exc:
        raise JammingModelError("target_signal 必须能转换为 complex128 数组。") from exc

    if array.ndim != 1:
        raise JammingModelError("target_signal 必须是一维数组。")
    if array.size == 0:
        raise JammingModelError("target_signal 不能为空。")
    if not np.all(np.isfinite(array)):
        raise JammingModelError("target_signal 必须只包含有限数值。")
    if not np.any(array):
        raise JammingModelError("target_signal 不能全零。")
    return array


def compute_average_target_sample_power(target_signal: npt.ArrayLike) -> float:
    """计算目标平均采样功率 P_s_avg = mean(abs(target_signal) ** 2)。"""
    signal = validate_signal_for_jamming(target_signal)
    average_power = float(np.mean(np.abs(signal) ** 2))
    if not math.isfinite(average_power) or average_power <= 0:
        raise JammingModelError("average_target_sample_power 必须是有限正数。")
    return average_power


def compute_jammer_variance_from_jsr(
    target_signal: npt.ArrayLike,
    jsr_linear: float,
) -> float:
    """根据 JSR 计算宽带噪声压制干扰方差。"""
    _validate_jsr_linear(jsr_linear)
    return float(jsr_linear * compute_average_target_sample_power(target_signal))


def compute_wideband_noise_jammed_output_sinr_linear(
    target_signal: npt.ArrayLike,
    noise_variance: float,
    jsr_linear: float,
) -> float:
    """计算宽带噪声压制干扰下的匹配滤波输出 SINR。"""
    _validate_noise_variance(noise_variance)
    jammer_variance = compute_jammer_variance_from_jsr(target_signal, jsr_linear)
    signal_energy = _compute_signal_energy_as_jamming_error(target_signal)
    return float(signal_energy / (noise_variance + jammer_variance))


def compute_pd_retention(clean_pd: float, jammed_pd: float) -> float:
    """计算检测概率保持率 pd_retention = jammed_pd / clean_pd。"""
    if not math.isfinite(clean_pd) or not 0.0 < clean_pd <= 1.0:
        raise JammingModelError("clean_pd 必须满足 0 < clean_pd <= 1。")
    if not math.isfinite(jammed_pd) or not 0.0 <= jammed_pd <= 1.0:
        raise JammingModelError("jammed_pd 必须满足 0 <= jammed_pd <= 1。")
    if jammed_pd - clean_pd > _PD_TOLERANCE:
        raise JammingModelError("jammed_pd 不应大于 clean_pd。")
    return float(jammed_pd / clean_pd)


def compute_wideband_noise_jamming_margin_jsr_linear(
    target_signal: npt.ArrayLike,
    noise_variance: float,
    pfa: float,
    target_pd: float,
) -> float:
    """解析计算给定 target_pd 和 pfa 下可承受的最大 JSR。"""
    _validate_noise_variance(noise_variance)
    _validate_margin_probabilities(pfa, target_pd)

    signal_energy = _compute_signal_energy_as_jamming_error(target_signal)
    average_power = compute_average_target_sample_power(target_signal)
    required_gamma = _compute_required_output_snr_as_jamming_error(target_pd, pfa)
    clean_gamma = signal_energy / noise_variance
    if clean_gamma < required_gamma:
        raise JammingModelError("无干扰场景无法满足 target_pd，抗干扰裕度不可定义。")

    sigma_total_max = signal_energy / required_gamma
    jammer_variance_max = sigma_total_max - noise_variance
    if jammer_variance_max < -_VARIANCE_TOLERANCE:
        raise JammingModelError("最大允许干扰方差为负，抗干扰裕度不可定义。")
    if jammer_variance_max < 0:
        jammer_variance_max = 0.0

    return float(jammer_variance_max / average_power)


def compute_wideband_noise_jamming_margin_jsr_db(
    target_signal: npt.ArrayLike,
    noise_variance: float,
    pfa: float,
    target_pd: float,
) -> float:
    """计算宽带噪声压制干扰抗干扰裕度，单位 dB。"""
    margin_linear = compute_wideband_noise_jamming_margin_jsr_linear(
        target_signal,
        noise_variance,
        pfa,
        target_pd,
    )
    if margin_linear == 0:
        return -math.inf
    return linear_to_db(margin_linear)


def compute_wideband_noise_jamming_metrics(
    target_signal: npt.ArrayLike,
    noise_variance: float,
    pfa: float,
    jsr_db: float,
    target_pd: float | None = None,
) -> JammingMetrics:
    """汇总宽带复高斯噪声压制干扰模型下的抗干扰性能指标。"""
    _validate_noise_variance(noise_variance)
    _validate_probability_as_jamming_error(pfa, "pfa")
    signal = validate_signal_for_jamming(target_signal)
    jsr_linear = db_to_linear(jsr_db)
    signal_energy = _compute_signal_energy_as_jamming_error(signal)
    average_power = compute_average_target_sample_power(signal)
    jammer_variance = compute_jammer_variance_from_jsr(signal, jsr_linear)
    total_disturbance_variance = noise_variance + jammer_variance
    clean_output_snr_linear = _compute_output_snr_as_jamming_error(signal, noise_variance)
    jammed_output_sinr_linear = signal_energy / total_disturbance_variance
    clean_pd = _compute_pd_as_jamming_error(clean_output_snr_linear, pfa)
    jammed_pd = _compute_pd_as_jamming_error(jammed_output_sinr_linear, pfa)
    pd_retention = compute_pd_retention(clean_pd, jammed_pd)

    jamming_margin_jsr_linear: float | None = None
    jamming_margin_jsr_db: float | None = None
    if target_pd is not None:
        jamming_margin_jsr_linear = compute_wideband_noise_jamming_margin_jsr_linear(
            signal,
            noise_variance,
            pfa,
            target_pd,
        )
        jamming_margin_jsr_db = (
            -math.inf
            if jamming_margin_jsr_linear == 0
            else linear_to_db(jamming_margin_jsr_linear)
        )

    return JammingMetrics(
        pfa=_validate_probability_as_jamming_error(pfa, "pfa"),
        jsr_linear=jsr_linear,
        jsr_db=float(jsr_db),
        signal_energy=signal_energy,
        average_target_sample_power=average_power,
        noise_variance=float(noise_variance),
        jammer_variance=jammer_variance,
        total_disturbance_variance=total_disturbance_variance,
        clean_output_snr_linear=clean_output_snr_linear,
        clean_output_snr_db=linear_to_db(clean_output_snr_linear),
        jammed_output_sinr_linear=jammed_output_sinr_linear,
        jammed_output_sinr_db=linear_to_db(jammed_output_sinr_linear),
        clean_pd=clean_pd,
        jammed_pd=jammed_pd,
        pd_retention=pd_retention,
        target_pd=None
        if target_pd is None
        else _validate_probability_as_jamming_error(target_pd, "target_pd"),
        jamming_margin_jsr_linear=jamming_margin_jsr_linear,
        jamming_margin_jsr_db=jamming_margin_jsr_db,
    )


def _validate_noise_variance(noise_variance: float) -> None:
    """校验热噪声方差为有限正数。"""
    if not math.isfinite(noise_variance) or noise_variance <= 0:
        raise JammingModelError("noise_variance 必须是有限正数。")


def _validate_jsr_linear(jsr_linear: float) -> None:
    """校验 JSR 线性值为有限非负数。"""
    if not math.isfinite(jsr_linear) or jsr_linear < 0:
        raise JammingModelError("jsr_linear 必须是有限非负数。")


def _validate_probability_as_jamming_error(value: float, name: str) -> float:
    """将 detection 概率校验错误转换为 JammingModelError。"""
    try:
        return validate_probability(value, name)
    except DetectionModelError as exc:
        raise JammingModelError(str(exc)) from exc


def _validate_margin_probabilities(pfa: float, target_pd: float) -> None:
    """校验抗干扰裕度所需概率条件。"""
    validated_pfa = _validate_probability_as_jamming_error(pfa, "pfa")
    validated_target_pd = _validate_probability_as_jamming_error(target_pd, "target_pd")
    if validated_target_pd <= validated_pfa:
        raise JammingModelError("target_pd 必须严格大于 pfa，抗干扰裕度才有定义。")


def _compute_signal_energy_as_jamming_error(target_signal: npt.ArrayLike) -> float:
    """将 detection 信号能量错误转换为 JammingModelError。"""
    try:
        return compute_signal_energy(target_signal)
    except DetectionModelError as exc:
        raise JammingModelError(str(exc)) from exc


def _compute_output_snr_as_jamming_error(
    target_signal: npt.ArrayLike,
    noise_variance: float,
) -> float:
    """将 detection 输出 SNR 错误转换为 JammingModelError。"""
    try:
        return compute_matched_filter_output_snr_linear(target_signal, noise_variance)
    except DetectionModelError as exc:
        raise JammingModelError(str(exc)) from exc


def _compute_pd_as_jamming_error(output_snr_linear: float, pfa: float) -> float:
    """将 detection Pd 错误转换为 JammingModelError。"""
    try:
        return compute_pd_square_law(output_snr_linear, pfa)
    except DetectionModelError as exc:
        raise JammingModelError(str(exc)) from exc


def _compute_required_output_snr_as_jamming_error(target_pd: float, pfa: float) -> float:
    """将 detection required SNR 错误转换为 JammingModelError。"""
    try:
        return compute_required_output_snr_linear(target_pd, pfa)
    except DetectionModelError as exc:
        raise JammingModelError(str(exc)) from exc
