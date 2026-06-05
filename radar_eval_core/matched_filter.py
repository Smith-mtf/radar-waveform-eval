"""离散时间匹配滤波和零多普勒旁瓣指标。"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from .schemas import MainlobeSpec, ZeroDopplerSidelobeMetrics


class MatchedFilterError(ValueError):
    """匹配滤波输入不满足离散一维非零信号要求。"""


class MainlobeDetectionError(ValueError):
    """主瓣边界无法按给定 MainlobeSpec 严格确定。"""


def matched_filter(
    rx: npt.ArrayLike,
    tx: npt.ArrayLike,
) -> npt.NDArray[np.complex128]:
    """执行离散时间匹配滤波，滤波器定义为 conj(tx[::-1])。"""
    rx_signal = _validate_matched_filter_signal(rx, "rx")
    tx_signal = _validate_matched_filter_signal(tx, "tx")
    result = np.convolve(rx_signal, np.conj(tx_signal[::-1]), mode="full")
    return result.astype(np.complex128, copy=False)


def autocorrelation_matched_filter(tx: npt.ArrayLike) -> npt.NDArray[np.complex128]:
    """对 tx 做自匹配滤波，等价于相同采样和归一化约定下的零多普勒模糊函数切片。"""
    return matched_filter(tx, tx)


def find_mainlobe_bounds(
    magnitude: npt.ArrayLike,
    peak_index: int,
    spec: MainlobeSpec,
) -> tuple[int, int]:
    """按显式 MainlobeSpec 查找主瓣边界；边界选择会决定 PSLR 和 ISLR。"""
    mag = _validate_magnitude(magnitude)
    if peak_index < 0 or peak_index >= mag.size:
        raise MainlobeDetectionError("peak_index 超出 magnitude 范围。")
    if mag[peak_index] <= 0:
        raise MainlobeDetectionError("peak_index 对应幅度必须大于 0。")

    if spec.method == "manual_guard_samples":
        return _find_manual_guard_bounds(mag, peak_index, spec)
    if spec.method == "first_local_minimum":
        return _find_first_local_minimum_bounds(mag, peak_index)
    if spec.method == "null_to_null":
        return _find_null_to_null_bounds(mag, peak_index, spec)

    raise MainlobeDetectionError(f"不支持的主瓣检测方法: {spec.method}")


def compute_zero_doppler_pslr_db(pc: npt.ArrayLike, spec: MainlobeSpec) -> float:
    """计算零多普勒峰值旁瓣比，定义为 20 * log10(A_side / A_main)。"""
    magnitude = _validate_pulse_compression_output(pc)
    peak_index = int(np.argmax(magnitude))
    left, right = find_mainlobe_bounds(magnitude, peak_index, spec)
    sidelobes = _extract_sidelobes(magnitude, left, right)
    if sidelobes.size == 0:
        return -math.inf

    side_magnitude = float(np.max(sidelobes))
    if side_magnitude == 0:
        return -math.inf

    main_magnitude = float(magnitude[peak_index])
    return float(20.0 * math.log10(side_magnitude / main_magnitude))


def compute_zero_doppler_islr_db(pc: npt.ArrayLike, spec: MainlobeSpec) -> float:
    """计算零多普勒积分旁瓣比，定义为 10 * log10(E_side / E_main)。"""
    magnitude = _validate_pulse_compression_output(pc)
    peak_index = int(np.argmax(magnitude))
    left, right = find_mainlobe_bounds(magnitude, peak_index, spec)

    mainlobe = magnitude[left : right + 1]
    sidelobes = _extract_sidelobes(magnitude, left, right)
    if sidelobes.size == 0:
        return -math.inf

    main_energy = float(np.sum(mainlobe**2))
    side_energy = float(np.sum(sidelobes**2))
    if side_energy == 0:
        return -math.inf

    return float(10.0 * math.log10(side_energy / main_energy))


def compute_mainlobe_width_samples(pc: npt.ArrayLike, spec: MainlobeSpec) -> int:
    """计算主瓣宽度，单位为 samples，定义为 right - left + 1。"""
    magnitude = _validate_pulse_compression_output(pc)
    peak_index = int(np.argmax(magnitude))
    left, right = find_mainlobe_bounds(magnitude, peak_index, spec)
    return right - left + 1


def compute_zero_doppler_sidelobe_metrics(
    tx: npt.ArrayLike,
    spec: MainlobeSpec,
) -> ZeroDopplerSidelobeMetrics:
    """由 tx 的自匹配滤波输出计算零多普勒旁瓣结构化指标。"""
    pc = autocorrelation_matched_filter(tx)
    magnitude = np.abs(pc)
    peak_index = int(np.argmax(magnitude))
    left, right = find_mainlobe_bounds(magnitude, peak_index, spec)

    return ZeroDopplerSidelobeMetrics(
        peak_index=peak_index,
        peak_magnitude=float(magnitude[peak_index]),
        mainlobe_left_index=left,
        mainlobe_right_index=right,
        mainlobe_width_samples=right - left + 1,
        zero_doppler_pslr_db=compute_zero_doppler_pslr_db(pc, spec),
        zero_doppler_islr_db=compute_zero_doppler_islr_db(pc, spec),
    )


def run_matched_filter() -> None:
    """保留旧占位入口；请直接调用 matched_filter 或 autocorrelation_matched_filter。"""
    raise NotImplementedError("请使用 matched_filter 或 autocorrelation_matched_filter。")


def _validate_matched_filter_signal(
    signal: npt.ArrayLike,
    name: str,
) -> npt.NDArray[np.complex128]:
    """校验匹配滤波输入为一维非空非零信号。"""
    array = np.asarray(signal)
    if array.ndim != 1:
        raise MatchedFilterError(f"{name} 必须是一维数组。")
    if array.size == 0:
        raise MatchedFilterError(f"{name} 不能为空。")
    if not np.any(array):
        raise MatchedFilterError(f"{name} 不能全零。")
    return array.astype(np.complex128, copy=False)


def _validate_magnitude(magnitude: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """校验幅度序列为一维非空非零数组。"""
    mag = np.asarray(magnitude, dtype=np.float64)
    if mag.ndim != 1:
        raise MainlobeDetectionError("magnitude 必须是一维数组。")
    if mag.size == 0:
        raise MainlobeDetectionError("magnitude 不能为空。")
    if not np.any(mag):
        raise MainlobeDetectionError("magnitude 不能全零。")
    if np.any(mag < 0):
        raise MainlobeDetectionError("magnitude 不能包含负值。")
    return mag


def _validate_pulse_compression_output(pc: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """校验脉压输出并返回幅度序列。"""
    array = np.asarray(pc)
    if array.ndim != 1:
        raise ValueError("pc 必须是一维数组。")
    if array.size == 0:
        raise ValueError("pc 不能为空。")

    magnitude = np.abs(array).astype(np.float64, copy=False)
    if not np.any(magnitude):
        raise ValueError("pc 不能全零。")
    return magnitude


def _find_manual_guard_bounds(
    magnitude: npt.NDArray[np.float64],
    peak_index: int,
    spec: MainlobeSpec,
) -> tuple[int, int]:
    """按手动 guard_samples 定义主瓣边界。"""
    if spec.guard_samples is None:
        raise ValueError("manual_guard_samples 方法必须提供 guard_samples。")

    left = peak_index - spec.guard_samples
    right = peak_index + spec.guard_samples
    if left < 0 or right >= magnitude.size:
        raise MainlobeDetectionError("manual_guard_samples 主瓣边界超出数组范围。")
    return left, right


def _find_first_local_minimum_bounds(
    magnitude: npt.NDArray[np.float64],
    peak_index: int,
) -> tuple[int, int]:
    """查找主峰左右第一个局部极小值。"""
    left = _find_left_local_minimum(magnitude, peak_index)
    right = _find_right_local_minimum(magnitude, peak_index)
    if left is None or right is None:
        raise MainlobeDetectionError("未能在主峰两侧找到局部极小值。")
    return left, right


def _find_left_local_minimum(
    magnitude: npt.NDArray[np.float64],
    peak_index: int,
) -> int | None:
    """从主峰向左查找第一个局部极小值。"""
    for index in range(peak_index - 1, 0, -1):
        if magnitude[index] <= magnitude[index - 1] and magnitude[index] <= magnitude[index + 1]:
            return index
    return None


def _find_right_local_minimum(
    magnitude: npt.NDArray[np.float64],
    peak_index: int,
) -> int | None:
    """从主峰向右查找第一个局部极小值。"""
    for index in range(peak_index + 1, magnitude.size - 1):
        if magnitude[index] <= magnitude[index - 1] and magnitude[index] <= magnitude[index + 1]:
            return index
    return None


def _find_null_to_null_bounds(
    magnitude: npt.NDArray[np.float64],
    peak_index: int,
    spec: MainlobeSpec,
) -> tuple[int, int]:
    """查找主峰左右第一个相对零点。"""
    peak_magnitude = float(magnitude[peak_index])
    threshold = spec.null_tolerance * peak_magnitude

    left_candidates = np.flatnonzero(magnitude[:peak_index] <= threshold)
    right_candidates = np.flatnonzero(magnitude[peak_index + 1 :] <= threshold)
    if left_candidates.size == 0 or right_candidates.size == 0:
        raise MainlobeDetectionError("未能在主峰两侧找到满足 null_tolerance 的零点。")

    left = int(left_candidates[-1])
    right = int(peak_index + 1 + right_candidates[0])
    return left, right


def _extract_sidelobes(
    magnitude: npt.NDArray[np.float64],
    left: int,
    right: int,
) -> npt.NDArray[np.float64]:
    """提取主瓣范围外的旁瓣采样点。"""
    return np.concatenate((magnitude[:left], magnitude[right + 1 :]))
