"""离散非周期二维模糊函数和多普勒容忍性指标。"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
from scipy.fft import fft, ifft, next_fast_len

from .schemas import AmbiguityFunctionResult, DopplerToleranceMetrics


class AmbiguityFunctionError(ValueError):
    """模糊函数输入或切片定义不满足严格计算要求。"""


class DopplerToleranceError(ValueError):
    """多普勒容忍性 crossing 无法在给定网格上严格确定。"""


def validate_signal_1d(signal: npt.ArrayLike) -> npt.NDArray[np.complex128]:
    """校验输入为一维、非空、非全零信号，并返回 complex128 数组。"""
    try:
        array = np.asarray(signal, dtype=np.complex128)
    except (TypeError, ValueError) as exc:
        raise AmbiguityFunctionError("signal 必须能转换为 complex128 数组。") from exc

    if array.ndim != 1:
        raise AmbiguityFunctionError("signal 必须是一维数组。")
    if array.size == 0:
        raise AmbiguityFunctionError("signal 不能为空。")
    if not np.any(array):
        raise AmbiguityFunctionError("signal 不能全零。")
    return array


def default_delay_samples(num_samples: int) -> npt.NDArray[np.int_]:
    """返回非周期相关默认 delay grid：-(N - 1) 到 +(N - 1)。"""
    if num_samples < 1:
        raise AmbiguityFunctionError("num_samples 必须大于等于 1。")
    return np.arange(-(num_samples - 1), num_samples, dtype=int)


def validate_doppler_grid(
    doppler_hz: npt.ArrayLike,
    sample_rate_hz: float,
) -> npt.NDArray[np.float64]:
    """校验 Doppler 网格一维、非空、严格递增、包含唯一 0 且位于 Nyquist 范围内。"""
    if sample_rate_hz <= 0:
        raise AmbiguityFunctionError("sample_rate_hz 必须大于 0。")

    try:
        doppler = np.asarray(doppler_hz, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise AmbiguityFunctionError("doppler_hz 必须能转换为 float64 数组。") from exc

    if doppler.ndim != 1:
        raise AmbiguityFunctionError("doppler_hz 必须是一维数组。")
    if doppler.size == 0:
        raise AmbiguityFunctionError("doppler_hz 不能为空。")
    if np.any(np.diff(doppler) <= 0):
        raise AmbiguityFunctionError("doppler_hz 必须严格递增。")
    if np.flatnonzero(doppler == 0.0).size != 1:
        raise AmbiguityFunctionError("doppler_hz 必须包含唯一的 0.0。")

    nyquist_doppler_hz = sample_rate_hz / 2.0
    if doppler[0] < -nyquist_doppler_hz or doppler[-1] > nyquist_doppler_hz:
        raise AmbiguityFunctionError("doppler_hz 必须位于 [-sample_rate_hz/2, sample_rate_hz/2]。")

    return doppler


def compute_ambiguity_function(
    signal: npt.ArrayLike,
    sample_rate_hz: float,
    doppler_hz: npt.ArrayLike,
    delay_samples: npt.ArrayLike | None = None,
) -> AmbiguityFunctionResult:
    """按离散非周期定义计算二维模糊函数矩阵。"""
    s = validate_signal_1d(signal)
    doppler = validate_doppler_grid(doppler_hz, sample_rate_hz)
    delays = _validate_delay_samples(delay_samples, s.size)
    sample_interval_s = 1.0 / sample_rate_hz
    sample_indices = np.arange(s.size, dtype=np.float64)
    fft_length = _next_linear_correlation_fft_length(s.size)

    ambiguity_complex = np.empty((doppler.size, delays.size), dtype=np.complex128)
    for doppler_index, doppler_frequency_hz in enumerate(doppler):
        doppler_shifted_signal = s * np.exp(
            -1j
            * 2.0
            * math.pi
            * doppler_frequency_hz
            * sample_indices
            * sample_interval_s,
        )
        ambiguity_complex[doppler_index, :] = _linear_correlation_fft_by_delay(
            doppler_shifted_signal,
            s,
            fft_length,
            delays,
        )

    ambiguity_magnitude = np.abs(ambiguity_complex).astype(np.float64, copy=False)
    peak_magnitude = float(np.max(ambiguity_magnitude))
    if peak_magnitude <= 0:
        raise AmbiguityFunctionError("ambiguity peak_magnitude 必须大于 0。")

    peak_doppler_index, peak_delay_index = np.unravel_index(
        int(np.argmax(ambiguity_magnitude)),
        ambiguity_magnitude.shape,
    )
    return AmbiguityFunctionResult(
        delay_samples=delays,
        delay_seconds=delays.astype(np.float64) / sample_rate_hz,
        doppler_hz=doppler,
        ambiguity_complex=ambiguity_complex,
        ambiguity_magnitude=ambiguity_magnitude,
        ambiguity_magnitude_normalized=ambiguity_magnitude / peak_magnitude,
        peak_magnitude=peak_magnitude,
        peak_delay_samples=int(delays[peak_delay_index]),
        peak_doppler_hz=float(doppler[peak_doppler_index]),
        sample_rate_hz=sample_rate_hz,
        metadata={
            "definition": "sum_n s[n] * conj(s[n - m]) * exp(-j * 2*pi * fd * n * Ts)",
            "correlation_type": "aperiodic",
            "matrix_shape": "doppler_by_delay",
            "normalization": "ambiguity_magnitude / peak_magnitude",
            "correlation_algorithm": "fft_linear_zero_padded",
            "fft_length": int(fft_length),
        },
    )


def get_zero_doppler_cut(
    result: AmbiguityFunctionResult,
) -> tuple[npt.NDArray[np.int_], npt.NDArray[np.float64]]:
    """返回 fd = 0 的 delay cut 归一化幅度。"""
    zero_indices = np.flatnonzero(result.doppler_hz == 0.0)
    if zero_indices.size != 1:
        raise AmbiguityFunctionError("result.doppler_hz 必须包含唯一的 0.0。")
    return result.delay_samples, result.ambiguity_magnitude_normalized[int(zero_indices[0]), :]


def get_zero_delay_doppler_cut(
    result: AmbiguityFunctionResult,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """返回 delay = 0 的 Doppler cut 归一化幅度。"""
    zero_indices = np.flatnonzero(result.delay_samples == 0)
    if zero_indices.size != 1:
        raise AmbiguityFunctionError("result.delay_samples 必须包含唯一的 0。")
    return result.doppler_hz, result.ambiguity_magnitude_normalized[:, int(zero_indices[0])]


def compute_doppler_tolerance(
    result: AmbiguityFunctionResult,
    loss_db: float = 3.0,
) -> DopplerToleranceMetrics:
    """基于 zero-delay Doppler cut 计算多普勒容忍性，结果依赖 Doppler 网格范围和分辨率。"""
    if loss_db <= 0:
        raise DopplerToleranceError("loss_db 必须大于 0。")

    doppler, zero_delay_cut = get_zero_delay_doppler_cut(result)
    zero_doppler_indices = np.flatnonzero(doppler == 0.0)
    if zero_doppler_indices.size != 1:
        raise DopplerToleranceError("doppler_hz 必须包含唯一的 0.0。")

    zero_index = int(zero_doppler_indices[0])
    zero_delay_peak_magnitude = float(zero_delay_cut[zero_index])
    if zero_delay_peak_magnitude <= 0:
        raise DopplerToleranceError("fd = 0 处的 zero-delay 响应必须大于 0。")

    relative_response = zero_delay_cut / zero_delay_peak_magnitude
    threshold_linear = 10.0 ** (-loss_db / 20.0)
    negative_crossing_hz = _find_negative_crossing(
        doppler,
        relative_response,
        zero_index,
        threshold_linear,
    )
    positive_crossing_hz = _find_positive_crossing(
        doppler,
        relative_response,
        zero_index,
        threshold_linear,
    )

    return DopplerToleranceMetrics(
        loss_db=float(loss_db),
        threshold_linear=float(threshold_linear),
        negative_crossing_hz=negative_crossing_hz,
        positive_crossing_hz=positive_crossing_hz,
        doppler_tolerance_hz=float(min(abs(negative_crossing_hz), abs(positive_crossing_hz))),
        zero_delay_peak_magnitude=zero_delay_peak_magnitude,
    )


def calculate_ambiguity_function() -> None:
    """保留旧占位入口；请直接调用 compute_ambiguity_function。"""
    raise NotImplementedError("请使用 compute_ambiguity_function。")


def _validate_delay_samples(
    delay_samples: npt.ArrayLike | None,
    num_samples: int,
) -> npt.NDArray[np.int_]:
    """校验 delay grid 为一维整数数组且位于非周期相关有效范围内。"""
    if delay_samples is None:
        return default_delay_samples(num_samples)

    delays = np.asarray(delay_samples)
    if delays.ndim != 1:
        raise AmbiguityFunctionError("delay_samples 必须是一维数组。")
    if delays.size == 0:
        raise AmbiguityFunctionError("delay_samples 不能为空。")
    if not np.issubdtype(delays.dtype, np.integer):
        raise AmbiguityFunctionError("delay_samples 必须是整数数组。")

    min_delay = -(num_samples - 1)
    max_delay = num_samples - 1
    if np.any((delays < min_delay) | (delays > max_delay)):
        raise AmbiguityFunctionError("delay_samples 超出 [-(N - 1), +(N - 1)] 范围。")
    return delays.astype(int, copy=False)


def _valid_time_indices_for_delay(delay_samples: int, num_samples: int) -> npt.NDArray[np.int_]:
    """返回满足 0 <= n < N 且 0 <= n - m < N 的 n 索引。"""
    n_start = max(0, delay_samples)
    n_stop = min(num_samples, num_samples + delay_samples)
    return np.arange(n_start, n_stop, dtype=int)


def _next_linear_correlation_fft_length(num_samples: int) -> int:
    """返回能容纳长度 N 信号线性相关的 FFT 长度。"""
    if num_samples < 1:
        raise AmbiguityFunctionError("num_samples 必须大于等于 1。")
    return int(next_fast_len(2 * num_samples - 1))


def _linear_correlation_fft_by_delay(
    signal: npt.NDArray[np.complex128],
    reference: npt.NDArray[np.complex128],
    fft_length: int,
    selected_delays: npt.NDArray[np.int_],
) -> npt.NDArray[np.complex128]:
    """用补零 FFT 计算线性相关，并按 selected_delays 返回 delay 切片。"""
    num_samples = signal.size
    if reference.size != num_samples:
        raise AmbiguityFunctionError("signal 和 reference 长度必须一致。")
    if fft_length < 2 * num_samples - 1:
        raise AmbiguityFunctionError("fft_length 不能小于线性相关所需长度 2N - 1。")

    correlation = ifft(
        fft(signal, n=fft_length) * np.conj(fft(reference, n=fft_length)),
        n=fft_length,
    )
    shifted_correlation = np.fft.fftshift(correlation)
    valid_start = fft_length // 2 - (num_samples - 1)
    valid_stop = valid_start + (2 * num_samples - 1)
    valid_correlation = shifted_correlation[valid_start:valid_stop]
    delay_indices = selected_delays + (num_samples - 1)
    return valid_correlation[delay_indices].astype(np.complex128, copy=False)


def _find_negative_crossing(
    doppler_hz: npt.NDArray[np.float64],
    response: npt.NDArray[np.float64],
    zero_index: int,
    threshold: float,
) -> float:
    """从 fd = 0 向负 Doppler 方向查找阈值 crossing。"""
    for inner_index in range(zero_index, 0, -1):
        outer_index = inner_index - 1
        if response[inner_index] >= threshold and response[outer_index] < threshold:
            return _interpolate_crossing(
                doppler_hz[inner_index],
                response[inner_index],
                doppler_hz[outer_index],
                response[outer_index],
                threshold,
            )
    raise DopplerToleranceError("负 Doppler 方向未找到阈值 crossing。")


def _find_positive_crossing(
    doppler_hz: npt.NDArray[np.float64],
    response: npt.NDArray[np.float64],
    zero_index: int,
    threshold: float,
) -> float:
    """从 fd = 0 向正 Doppler 方向查找阈值 crossing。"""
    for inner_index in range(zero_index, response.size - 1):
        outer_index = inner_index + 1
        if response[inner_index] >= threshold and response[outer_index] < threshold:
            return _interpolate_crossing(
                doppler_hz[inner_index],
                response[inner_index],
                doppler_hz[outer_index],
                response[outer_index],
                threshold,
            )
    raise DopplerToleranceError("正 Doppler 方向未找到阈值 crossing。")


def _interpolate_crossing(
    x_inner: float,
    y_inner: float,
    x_outer: float,
    y_outer: float,
    threshold: float,
) -> float:
    """在线性段上插值计算阈值 crossing 位置。"""
    if y_outer == y_inner:
        raise DopplerToleranceError("无法在响应相等的网格点之间插值 crossing。")
    return float(x_inner + (threshold - y_inner) * (x_outer - x_inner) / (y_outer - y_inner))
