"""工程可实现性相关指标。"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def compute_average_power(iq: npt.NDArray[np.complexfloating]) -> float:
    """计算复 IQ 信号的平均功率，定义为 mean(abs(iq)^2)。"""
    signal = _validate_one_dimensional_signal(iq)
    return float(np.mean(np.abs(signal) ** 2))


def compute_peak_power(iq: npt.NDArray[np.complexfloating]) -> float:
    """计算复 IQ 信号的峰值功率，定义为 max(abs(iq)^2)。"""
    signal = _validate_one_dimensional_signal(iq)
    return float(np.max(np.abs(signal) ** 2))


def compute_papr_db(iq: npt.NDArray[np.complexfloating]) -> float:
    """计算峰均功率比，定义为 10 * log10(peak_power / average_power)。"""
    average_power = compute_average_power(iq)
    if average_power <= 0:
        raise ValueError("平均功率必须大于 0，才能计算 PAPR。")

    peak_power = compute_peak_power(iq)
    return float(10.0 * np.log10(peak_power / average_power))


def compute_tbp(bandwidth_hz: float, pulse_width_s: float) -> float:
    """计算时间带宽积，定义为 bandwidth_hz * pulse_width_s。"""
    if bandwidth_hz <= 0:
        raise ValueError("bandwidth_hz 必须大于 0。")
    if pulse_width_s <= 0:
        raise ValueError("pulse_width_s 必须大于 0。")

    return float(bandwidth_hz * pulse_width_s)


def compute_nominal_avg_psd_w_per_hz(average_power_w: float, bandwidth_hz: float) -> float:
    """计算给定带宽内功率均匀分布条件下的名义平均 PSD。"""
    if average_power_w < 0:
        raise ValueError("average_power_w 不能为负。")
    if bandwidth_hz <= 0:
        raise ValueError("bandwidth_hz 必须大于 0。")

    return float(average_power_w / bandwidth_hz)


def compute_psd_avg_w_per_hz(average_power_w: float, bandwidth_hz: float) -> float:
    """兼容旧名称；请改用 compute_nominal_avg_psd_w_per_hz。"""
    return compute_nominal_avg_psd_w_per_hz(average_power_w, bandwidth_hz)


def _validate_one_dimensional_signal(
    iq: npt.NDArray[np.complexfloating],
) -> npt.NDArray[np.complexfloating]:
    """校验 IQ 信号为一维非空数组。"""
    signal = np.asarray(iq)
    if signal.ndim != 1:
        raise ValueError("IQ 信号必须是一维数组。")
    if signal.size == 0:
        raise ValueError("IQ 信号不能为空。")
    return signal
