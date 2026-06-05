"""探测性能模型测试。"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radar_eval_core.detection import (
    DetectionModelError,
    compute_average_sample_snr_linear,
    compute_detection_metrics,
    compute_detection_threshold_from_pfa,
    compute_matched_filter_output_snr_linear,
    compute_matched_filter_processing_gain_db,
    compute_pd_square_law,
    compute_pfa_from_threshold,
    compute_required_output_snr_linear,
    compute_signal_energy,
)


def test_threshold_from_pfa() -> None:
    """测试由 Pfa 计算归一化检测门限。"""
    threshold = compute_detection_threshold_from_pfa(1e-6)

    assert threshold == pytest.approx(-math.log(1e-6))


def test_pfa_from_threshold() -> None:
    """测试由归一化检测门限反算 Pfa。"""
    threshold = -math.log(1e-6)

    assert compute_pfa_from_threshold(threshold) == pytest.approx(1e-6)


def test_pd_equals_pfa_when_snr_zero() -> None:
    """测试输出 SNR 为 0 时 Pd 等于 Pfa。"""
    pfa = 1e-4

    assert compute_pd_square_law(0.0, pfa) == pytest.approx(pfa)


def test_pd_monotonic_increases_with_snr() -> None:
    """测试固定 Pfa 下 Pd 随输出 SNR 单调不下降。"""
    pfa = 1e-6
    pd_values = [compute_pd_square_law(snr, pfa) for snr in [0.0, 1.0, 10.0, 100.0]]

    assert pd_values == sorted(pd_values)


def test_lower_pfa_requires_higher_threshold() -> None:
    """测试更低 Pfa 对应更高门限。"""
    assert compute_detection_threshold_from_pfa(1e-6) > compute_detection_threshold_from_pfa(1e-3)


def test_required_snr_reaches_target_pd() -> None:
    """测试 required output SNR 反解后可达到目标 Pd。"""
    required_snr = compute_required_output_snr_linear(target_pd=0.9, pfa=1e-6)
    achieved_pd = compute_pd_square_law(required_snr, pfa=1e-6)

    assert achieved_pd == pytest.approx(0.9, abs=1e-6)


def test_required_snr_zero_when_target_pd_not_above_pfa() -> None:
    """测试 target_pd 不高于 Pfa 时所需输出 SNR 为 0。"""
    assert compute_required_output_snr_linear(target_pd=1e-4, pfa=1e-3) == 0.0


def test_output_snr_for_rectangular_signal() -> None:
    """测试矩形信号下平均采样 SNR、输出 SNR 和处理增益。"""
    num_samples = 16
    target_signal = np.ones(num_samples, dtype=np.complex128)

    assert compute_signal_energy(target_signal) == pytest.approx(num_samples)
    assert compute_average_sample_snr_linear(
        target_signal,
        noise_variance=1.0,
    ) == pytest.approx(1.0)
    assert compute_matched_filter_output_snr_linear(
        target_signal,
        noise_variance=1.0,
    ) == pytest.approx(
        num_samples,
    )
    assert compute_matched_filter_processing_gain_db(target_signal) == pytest.approx(
        10.0 * math.log10(num_samples),
    )


def test_detection_metrics_fields() -> None:
    """测试 DetectionMetrics 字段和数值合理。"""
    target_signal = np.ones(8, dtype=np.complex128)

    metrics = compute_detection_metrics(
        target_signal=target_signal,
        noise_variance=1.0,
        pfa=1e-6,
        target_pd=0.9,
    )

    assert metrics.model_name == "single_pulse_matched_filter_square_law_cawg"
    assert metrics.noise_model == "complex_awgn"
    assert metrics.target_model == "deterministic_nonfluctuating_unknown_phase"
    assert metrics.detector == "matched_filter_square_law"
    assert metrics.signal_energy == pytest.approx(8.0)
    assert metrics.average_sample_snr_linear == pytest.approx(1.0)
    assert metrics.output_snr_linear == pytest.approx(8.0)
    assert 0.0 <= metrics.pd <= 1.0
    assert metrics.target_pd == pytest.approx(0.9)
    assert metrics.required_output_snr_linear is not None
    assert metrics.required_output_snr_db is not None


def test_invalid_inputs_raise() -> None:
    """测试非法概率、噪声方差和信号输入会报错。"""
    valid_signal = np.ones(4, dtype=np.complex128)

    with pytest.raises(DetectionModelError):
        compute_detection_threshold_from_pfa(0.0)
    with pytest.raises(DetectionModelError):
        compute_detection_threshold_from_pfa(1.0)
    with pytest.raises(DetectionModelError):
        compute_required_output_snr_linear(target_pd=0.0, pfa=1e-3)
    with pytest.raises(DetectionModelError):
        compute_required_output_snr_linear(target_pd=1.0, pfa=1e-3)
    with pytest.raises(DetectionModelError):
        compute_average_sample_snr_linear(valid_signal, noise_variance=0.0)
    with pytest.raises(DetectionModelError):
        compute_signal_energy(np.array([], dtype=np.complex128))
    with pytest.raises(DetectionModelError):
        compute_signal_energy(np.zeros(4, dtype=np.complex128))
    with pytest.raises(DetectionModelError):
        compute_signal_energy(np.ones((2, 2), dtype=np.complex128))
