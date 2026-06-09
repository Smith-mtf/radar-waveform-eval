"""二维模糊函数和多普勒容忍性测试。"""

from __future__ import annotations

import numpy as np
import pytest

from radar_eval_core.ambiguity import (
    AmbiguityFunctionError,
    DopplerToleranceError,
    compute_ambiguity_function,
    compute_doppler_tolerance,
    default_delay_samples,
    get_zero_delay_doppler_cut,
    get_zero_doppler_cut,
    validate_doppler_grid,
    validate_signal_1d,
)
from radar_eval_core.matched_filter import autocorrelation_matched_filter


def test_default_delay_samples() -> None:
    """测试默认非周期 delay grid。"""
    assert np.array_equal(default_delay_samples(4), np.array([-3, -2, -1, 0, 1, 2, 3]))


def test_ambiguity_shape_and_normalization() -> None:
    """测试模糊函数矩阵形状和归一化峰值。"""
    signal = np.array([1 + 0j, 2 + 1j, -1 + 0.5j], dtype=np.complex128)
    doppler_hz = np.array([-10.0, 0.0, 10.0])

    result = compute_ambiguity_function(signal, sample_rate_hz=1_000.0, doppler_hz=doppler_hz)

    assert result.ambiguity_complex.shape == (len(doppler_hz), len(result.delay_samples))
    assert np.max(result.ambiguity_magnitude_normalized) == pytest.approx(1.0)


def test_ambiguity_fft_matches_direct_definition() -> None:
    """测试补零 FFT 实现与离散非周期定义逐项一致。"""
    signal = np.array([1 + 0.5j, -2 + 1j, 0.25 - 0.75j, 1.5 + 0j], dtype=np.complex128)
    sample_rate_hz = 2_000.0
    doppler_hz = np.array([-125.0, 0.0, 250.0])

    result = compute_ambiguity_function(
        signal,
        sample_rate_hz=sample_rate_hz,
        doppler_hz=doppler_hz,
    )
    expected = _direct_ambiguity(signal, sample_rate_hz, doppler_hz, result.delay_samples)

    assert np.allclose(result.ambiguity_complex, expected, atol=1e-12)
    assert result.metadata["correlation_algorithm"] == "fft_linear_zero_padded"


def test_ambiguity_fft_length_preserves_linear_delay_span() -> None:
    """测试补零 FFT 只返回有效线性相关 delay 区间。"""
    signal = np.zeros(10, dtype=np.complex128)
    signal[0] = 1.0
    signal[-1] = 2.0
    doppler_hz = np.array([-10.0, 0.0, 10.0])

    result = compute_ambiguity_function(signal, sample_rate_hz=1_000.0, doppler_hz=doppler_hz)

    assert len(result.delay_samples) == 2 * len(signal) - 1
    assert np.array_equal(result.delay_samples, default_delay_samples(len(signal)))
    assert result.metadata["fft_length"] >= 2 * len(signal) - 1
    zero_doppler_row = result.ambiguity_complex[1]
    nonzero_indices = np.flatnonzero(np.abs(zero_doppler_row) > 1e-12)
    assert np.array_equal(result.delay_samples[nonzero_indices], np.array([-9, 0, 9]))
    assert np.abs(zero_doppler_row[nonzero_indices]).tolist() == pytest.approx([2.0, 5.0, 2.0])


def test_custom_delay_subset_matches_full_result() -> None:
    """测试自定义 delay 子集保持请求顺序并匹配完整结果对应列。"""
    signal = np.array([1.0, -1.0j, 2.0 + 0.5j, -0.25, 0.75j], dtype=np.complex128)
    doppler_hz = np.array([-50.0, 0.0, 50.0])
    selected_delays = np.array([2, -4, 0], dtype=int)

    full = compute_ambiguity_function(signal, sample_rate_hz=1_000.0, doppler_hz=doppler_hz)
    subset = compute_ambiguity_function(
        signal,
        sample_rate_hz=1_000.0,
        doppler_hz=doppler_hz,
        delay_samples=selected_delays,
    )

    expected_columns = [
        int(np.flatnonzero(full.delay_samples == delay)[0])
        for delay in selected_delays
    ]
    assert np.array_equal(subset.delay_samples, selected_delays)
    assert np.allclose(subset.ambiguity_complex, full.ambiguity_complex[:, expected_columns])


def test_zero_doppler_cut_matches_autocorrelation() -> None:
    """测试 zero-Doppler cut 与自匹配滤波输出在 delay 顺序下一致。"""
    signal = np.array([1 + 1j, 2 - 1j, -1 + 0.5j, 0.25 - 0.75j], dtype=np.complex128)
    doppler_hz = np.array([-25.0, 0.0, 25.0])

    result = compute_ambiguity_function(signal, sample_rate_hz=2_000.0, doppler_hz=doppler_hz)
    zero_doppler_index = int(np.flatnonzero(result.doppler_hz == 0.0)[0])
    zero_doppler_complex = result.ambiguity_complex[zero_doppler_index, :]
    autocorrelation = autocorrelation_matched_filter(signal)

    assert np.array_equal(result.delay_samples, default_delay_samples(len(signal)))
    assert np.allclose(zero_doppler_complex, autocorrelation)
    assert np.allclose(np.abs(zero_doppler_complex), np.abs(autocorrelation))


def test_zero_delay_doppler_cut_exists() -> None:
    """测试 zero-delay Doppler cut 可以获取，且 fd=0 处为归一化峰值。"""
    signal = np.ones(8, dtype=np.complex128)
    doppler_hz = np.linspace(-100.0, 100.0, 201)

    result = compute_ambiguity_function(signal, sample_rate_hz=1_000.0, doppler_hz=doppler_hz)
    cut_doppler, zero_delay_cut = get_zero_delay_doppler_cut(result)
    zero_index = int(np.flatnonzero(cut_doppler == 0.0)[0])

    assert zero_delay_cut[zero_index] == pytest.approx(1.0)


def test_zero_doppler_cut_exists() -> None:
    """测试 zero-Doppler delay cut 可以获取。"""
    signal = np.array([1.0, -1.0, 1.0], dtype=np.complex128)
    doppler_hz = np.array([-10.0, 0.0, 10.0])

    result = compute_ambiguity_function(signal, sample_rate_hz=1_000.0, doppler_hz=doppler_hz)
    delay_samples, zero_doppler_cut = get_zero_doppler_cut(result)

    assert np.array_equal(delay_samples, default_delay_samples(len(signal)))
    assert np.max(zero_doppler_cut) == pytest.approx(1.0)


def test_doppler_tolerance_for_rectangular_pulse() -> None:
    """测试矩形脉冲在足够 Doppler 网格上可以计算 3 dB 容忍性。"""
    signal = np.ones(64, dtype=np.complex128)
    doppler_hz = np.linspace(-30.0, 30.0, 1201)
    result = compute_ambiguity_function(signal, sample_rate_hz=1_000.0, doppler_hz=doppler_hz)

    metrics = compute_doppler_tolerance(result, loss_db=3.0)

    assert metrics.doppler_tolerance_hz > 0
    assert metrics.positive_crossing_hz > 0
    assert metrics.negative_crossing_hz < 0
    assert metrics.threshold_linear == pytest.approx(10.0 ** (-3.0 / 20.0))


def test_doppler_tolerance_raises_when_grid_too_narrow() -> None:
    """测试 Doppler 网格太窄时不返回网格边界。"""
    signal = np.ones(64, dtype=np.complex128)
    doppler_hz = np.linspace(-1.0, 1.0, 41)
    result = compute_ambiguity_function(signal, sample_rate_hz=1_000.0, doppler_hz=doppler_hz)

    with pytest.raises(DopplerToleranceError):
        compute_doppler_tolerance(result, loss_db=3.0)


def test_validate_doppler_grid_rejects_invalid_grid() -> None:
    """测试 Doppler grid 校验拒绝非法网格。"""
    with pytest.raises(AmbiguityFunctionError):
        validate_doppler_grid(np.array([-2.0, -1.0, 1.0]), sample_rate_hz=1_000.0)
    with pytest.raises(AmbiguityFunctionError):
        validate_doppler_grid(np.array([-1.0, 0.0, 0.5, 0.4]), sample_rate_hz=1_000.0)
    with pytest.raises(AmbiguityFunctionError):
        validate_doppler_grid(np.array([-600.0, 0.0, 600.0]), sample_rate_hz=1_000.0)
    with pytest.raises(AmbiguityFunctionError):
        validate_doppler_grid(np.array([], dtype=np.float64), sample_rate_hz=1_000.0)


def test_invalid_signal_raises() -> None:
    """测试 signal 校验拒绝空数组、全零数组和非一维数组。"""
    with pytest.raises(AmbiguityFunctionError):
        validate_signal_1d(np.array([], dtype=np.complex128))
    with pytest.raises(AmbiguityFunctionError):
        validate_signal_1d(np.zeros(4, dtype=np.complex128))
    with pytest.raises(AmbiguityFunctionError):
        validate_signal_1d(np.ones((2, 2), dtype=np.complex128))


def _direct_ambiguity(
    signal: np.ndarray,
    sample_rate_hz: float,
    doppler_hz: np.ndarray,
    delay_samples: np.ndarray,
) -> np.ndarray:
    output = np.empty((doppler_hz.size, delay_samples.size), dtype=np.complex128)
    sample_interval_s = 1.0 / sample_rate_hz
    num_samples = signal.size
    for doppler_index, doppler_frequency_hz in enumerate(doppler_hz):
        for delay_index, delay in enumerate(delay_samples):
            n_start = max(0, int(delay))
            n_stop = min(num_samples, num_samples + int(delay))
            n = np.arange(n_start, n_stop)
            output[doppler_index, delay_index] = np.sum(
                signal[n]
                * np.conj(signal[n - int(delay)])
                * np.exp(-1j * 2.0 * np.pi * doppler_frequency_hz * n * sample_interval_s),
            )
    return output
