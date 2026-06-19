"""反侦察 / 低截获波形暴露特征。"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
from scipy import signal as scipy_signal

from .engineering import (
    compute_average_power as _compute_engineering_average_power,
)
from .engineering import (
    compute_nominal_avg_psd_w_per_hz as _compute_engineering_nominal_avg_psd,
)
from .engineering import (
    compute_papr_db as _compute_engineering_papr_db,
)
from .engineering import (
    compute_peak_power as _compute_engineering_peak_power,
)
from .engineering import (
    compute_tbp as _compute_engineering_tbp,
)
from .schemas import LpiExposureMetrics, SpectrumEstimate

_PSD_POWER_RELATIVE_ERROR_TOLERANCE = 1e-6
_FREQUENCY_GRID_RTOL = 1e-9
_FREQUENCY_GRID_ATOL = 1e-12
_DUTY_CYCLE_RELATIVE_TOLERANCE = 1e-9


class LpiFeatureError(ValueError):
    """低截获暴露特征输入错误或指标不可定义。"""


def validate_signal_for_lpi(signal: npt.ArrayLike) -> npt.NDArray[np.complex128]:
    """校验波形信号为一维、非空、非全零的 complex128 数组。"""
    try:
        array = np.asarray(signal, dtype=np.complex128)
    except (TypeError, ValueError) as exc:
        raise LpiFeatureError("signal 必须能转换为 complex128 数组。") from exc

    if array.ndim != 1:
        raise LpiFeatureError("signal 必须是一维数组。")
    if array.size == 0:
        raise LpiFeatureError("signal 不能为空。")
    if not np.all(np.isfinite(array)):
        raise LpiFeatureError("signal 必须只包含有限数值。")
    if not np.any(array):
        raise LpiFeatureError("signal 不能全零。")
    return array


def validate_positive(value: float, name: str) -> float:
    """校验参数为有限正数。"""
    if not math.isfinite(value) or value <= 0:
        raise LpiFeatureError(f"{name} 必须是有限正数。")
    return float(value)


def compute_peak_power_w(signal: npt.ArrayLike) -> float:
    """计算峰值功率 peak_power_w = max(abs(signal) ** 2)。"""
    validated_signal = validate_signal_for_lpi(signal)
    try:
        return _compute_engineering_peak_power(validated_signal)
    except ValueError as exc:
        raise LpiFeatureError(str(exc)) from exc


def compute_average_power_w(signal: npt.ArrayLike) -> float:
    """计算平均功率 average_power_w = mean(abs(signal) ** 2)。"""
    validated_signal = validate_signal_for_lpi(signal)
    try:
        return _compute_engineering_average_power(validated_signal)
    except ValueError as exc:
        raise LpiFeatureError(str(exc)) from exc


def compute_papr_db(signal: npt.ArrayLike) -> float:
    """计算低截获暴露特征中的 PAPR，定义为 10 * log10(峰值功率 / 平均功率)。"""
    validated_signal = validate_signal_for_lpi(signal)
    try:
        return _compute_engineering_papr_db(validated_signal)
    except ValueError as exc:
        raise LpiFeatureError(str(exc)) from exc


def compute_nominal_avg_psd_w_per_hz(average_power_w: float, bandwidth_hz: float) -> float:
    """计算名义平均 PSD；该值不是真实频谱估计。"""
    if not math.isfinite(average_power_w) or average_power_w < 0:
        raise LpiFeatureError("average_power_w 必须是有限非负数。")
    validate_positive(bandwidth_hz, "bandwidth_hz")
    try:
        return _compute_engineering_nominal_avg_psd(average_power_w, bandwidth_hz)
    except ValueError as exc:
        raise LpiFeatureError(str(exc)) from exc


def compute_two_sided_periodogram_psd(
    signal: npt.ArrayLike,
    sample_rate_hz: float,
) -> SpectrumEstimate:
    """使用固定 boxcar 窗计算复基带双边 periodogram PSD。"""
    validated_signal = validate_signal_for_lpi(signal)
    validated_sample_rate_hz = validate_positive(sample_rate_hz, "sample_rate_hz")
    if validated_signal.size < 2:
        raise LpiFeatureError("periodogram PSD 至少需要 2 个采样点。")

    frequency_hz, psd_w_per_hz = scipy_signal.periodogram(
        validated_signal,
        fs=validated_sample_rate_hz,
        window="boxcar",
        detrend=False,
        return_onesided=False,
        scaling="density",
    )
    shifted_frequency_hz = np.fft.fftshift(frequency_hz).astype(np.float64, copy=False)
    shifted_psd_w_per_hz = np.fft.fftshift(psd_w_per_hz).astype(np.float64, copy=False)
    frequency_resolution_hz = _validate_frequency_grid(shifted_frequency_hz)
    if np.any(shifted_psd_w_per_hz < 0) or not np.all(np.isfinite(shifted_psd_w_per_hz)):
        raise LpiFeatureError("periodogram PSD 必须是有限非负数组。")

    total_power_from_psd_w = float(np.sum(shifted_psd_w_per_hz) * frequency_resolution_hz)
    average_power_time_domain_w = compute_average_power_w(validated_signal)
    if average_power_time_domain_w <= 0:
        raise LpiFeatureError("average_power_time_domain_w 必须大于 0。")

    relative_power_error = abs(
        total_power_from_psd_w - average_power_time_domain_w,
    ) / average_power_time_domain_w
    if relative_power_error > _PSD_POWER_RELATIVE_ERROR_TOLERANCE:
        raise LpiFeatureError("PSD 积分功率与时域平均功率不一致。")

    return SpectrumEstimate(
        frequency_hz=shifted_frequency_hz,
        psd_w_per_hz=shifted_psd_w_per_hz,
        frequency_resolution_hz=frequency_resolution_hz,
        total_power_from_psd_w=total_power_from_psd_w,
        average_power_time_domain_w=average_power_time_domain_w,
        relative_power_error=float(relative_power_error),
        method="two_sided_periodogram",
        window="boxcar",
        scaling="density",
        return_onesided=False,
    )


def compute_tbp(bandwidth_hz: float, pulse_width_s: float) -> float:
    """计算时宽带宽积 tbp = bandwidth_hz * pulse_width_s。"""
    validate_positive(bandwidth_hz, "bandwidth_hz")
    validate_positive(pulse_width_s, "pulse_width_s")
    try:
        return _compute_engineering_tbp(bandwidth_hz, pulse_width_s)
    except ValueError as exc:
        raise LpiFeatureError(str(exc)) from exc


def compute_duty_cycle(
    pulse_width_s: float,
    *,
    prf_hz: float | None = None,
    pri_s: float | None = None,
) -> float:
    """按 PRF 或 PRI 计算占空比，要求定义完整且 duty_cycle 不超过 1。"""
    validated_pulse_width_s = validate_positive(pulse_width_s, "pulse_width_s")
    if prf_hz is None and pri_s is None:
        raise LpiFeatureError("prf_hz 和 pri_s 至少需要提供一个。")

    validated_prf_hz: float | None = None
    validated_pri_s: float | None = None
    if prf_hz is not None:
        validated_prf_hz = validate_positive(prf_hz, "prf_hz")
    if pri_s is not None:
        validated_pri_s = validate_positive(pri_s, "pri_s")

    if validated_prf_hz is not None and validated_pri_s is not None:
        reciprocal_pri_hz = 1.0 / validated_pri_s
        if not math.isclose(
            validated_prf_hz,
            reciprocal_pri_hz,
            rel_tol=_DUTY_CYCLE_RELATIVE_TOLERANCE,
            abs_tol=0.0,
        ):
            raise LpiFeatureError("prf_hz 必须与 1 / pri_s 一致。")
        duty_cycle = validated_pulse_width_s * validated_prf_hz
    elif validated_prf_hz is not None:
        duty_cycle = validated_pulse_width_s * validated_prf_hz
    elif validated_pri_s is not None:
        duty_cycle = validated_pulse_width_s / validated_pri_s
    else:
        raise LpiFeatureError("prf_hz 和 pri_s 至少需要提供一个。")

    if not math.isfinite(duty_cycle) or not 0.0 < duty_cycle <= 1.0:
        raise LpiFeatureError("duty_cycle 必须满足 0 < duty_cycle <= 1。")
    return float(duty_cycle)


def compute_lpi_exposure_metrics(
    signal: npt.ArrayLike,
    *,
    sample_rate_hz: float,
    bandwidth_hz: float,
    pulse_width_s: float,
    prf_hz: float | None = None,
    pri_s: float | None = None,
) -> LpiExposureMetrics:
    """汇总波形低截获暴露特征；该函数不代表完整反侦察成功概率。"""
    validated_signal = validate_signal_for_lpi(signal)
    validated_sample_rate_hz = validate_positive(sample_rate_hz, "sample_rate_hz")
    validated_bandwidth_hz = validate_positive(bandwidth_hz, "bandwidth_hz")
    validated_pulse_width_s = validate_positive(pulse_width_s, "pulse_width_s")

    peak_power_w = compute_peak_power_w(validated_signal)
    average_power_w = compute_average_power_w(validated_signal)
    spectrum = compute_two_sided_periodogram_psd(validated_signal, validated_sample_rate_hz)

    duty_cycle: float | None = None
    duty_cycle_definition: str | None = None
    if prf_hz is not None or pri_s is not None:
        duty_cycle = compute_duty_cycle(validated_pulse_width_s, prf_hz=prf_hz, pri_s=pri_s)
        duty_cycle_definition = _duty_cycle_definition(prf_hz=prf_hz, pri_s=pri_s)

    return LpiExposureMetrics(
        peak_power_w=peak_power_w,
        average_power_w=average_power_w,
        papr_db=compute_papr_db(validated_signal),
        bandwidth_hz=validated_bandwidth_hz,
        pulse_width_s=validated_pulse_width_s,
        nominal_avg_psd_w_per_hz=compute_nominal_avg_psd_w_per_hz(
            average_power_w,
            validated_bandwidth_hz,
        ),
        tbp=compute_tbp(validated_bandwidth_hz, validated_pulse_width_s),
        psd_total_power_w=spectrum.total_power_from_psd_w,
        psd_relative_power_error=spectrum.relative_power_error,
        duty_cycle=duty_cycle,
        duty_cycle_definition=duty_cycle_definition,
    )


def _validate_frequency_grid(frequency_hz: npt.NDArray[np.float64]) -> float:
    """校验频率网格为一维、严格递增且等间隔。"""
    if frequency_hz.ndim != 1:
        raise LpiFeatureError("frequency_hz 必须是一维数组。")
    if frequency_hz.size < 2:
        raise LpiFeatureError("frequency_hz 至少需要 2 个频率点。")
    if not np.all(np.isfinite(frequency_hz)):
        raise LpiFeatureError("frequency_hz 必须只包含有限数值。")

    frequency_steps_hz = np.diff(frequency_hz)
    if not np.all(frequency_steps_hz > 0):
        raise LpiFeatureError("frequency_hz 必须严格递增，不能静默排序。")

    frequency_resolution_hz = float(frequency_steps_hz[0])
    if not np.allclose(
        frequency_steps_hz,
        frequency_resolution_hz,
        rtol=_FREQUENCY_GRID_RTOL,
        atol=_FREQUENCY_GRID_ATOL,
    ):
        raise LpiFeatureError("frequency_hz 必须为等间隔网格。")
    return frequency_resolution_hz


def _duty_cycle_definition(*, prf_hz: float | None, pri_s: float | None) -> str:
    """生成占空比定义描述。"""
    if prf_hz is not None and pri_s is not None:
        return "pulse_width_s * prf_hz, with prf_hz ~= 1 / pri_s"
    if prf_hz is not None:
        return "pulse_width_s * prf_hz"
    return "pulse_width_s / pri_s"
