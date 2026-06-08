"""宽带复高斯噪声压制干扰模型测试。"""

from __future__ import annotations

import numpy as np
import pytest

from radar_eval_core.detection import (
    compute_matched_filter_output_snr_linear,
    compute_pd_square_law,
)
from radar_eval_core.jamming import (
    JammingModelError,
    compute_average_target_sample_power,
    compute_jammer_variance_from_jsr,
    compute_pd_retention,
    compute_wideband_noise_jammed_output_sinr_linear,
    compute_wideband_noise_jamming_margin_jsr_linear,
    compute_wideband_noise_jamming_metrics,
)


def test_jammer_variance_from_jsr() -> None:
    """测试由 JSR 计算干扰方差。"""
    target_signal = np.ones(8, dtype=np.complex128)

    assert compute_average_target_sample_power(target_signal) == pytest.approx(1.0)
    assert compute_jammer_variance_from_jsr(target_signal, jsr_linear=10.0) == pytest.approx(10.0)


def test_jammed_sinr_decreases_with_jsr() -> None:
    """测试 JSR 增大时干扰下输出 SINR 单调下降。"""
    target_signal = np.ones(16, dtype=np.complex128)
    sinr_values = [
        compute_wideband_noise_jammed_output_sinr_linear(target_signal, 1.0, jsr)
        for jsr in [0.0, 1.0, 10.0]
    ]

    assert sinr_values == sorted(sinr_values, reverse=True)


def test_jsr_zero_matches_clean_snr() -> None:
    """测试 JSR 为 0 时干扰下 SINR 等于无干扰输出 SNR。"""
    target_signal = np.ones(16, dtype=np.complex128)
    clean_snr = compute_matched_filter_output_snr_linear(target_signal, noise_variance=1.0)
    jammed_sinr = compute_wideband_noise_jammed_output_sinr_linear(
        target_signal,
        noise_variance=1.0,
        jsr_linear=0.0,
    )

    assert jammed_sinr == pytest.approx(clean_snr)


def test_pd_under_jamming_decreases_with_jsr() -> None:
    """测试 JSR 增大时干扰下 Pd 单调不升。"""
    target_signal = np.ones(16, dtype=np.complex128)
    pfa = 1e-6
    pd_values = [
        compute_pd_square_law(
            compute_wideband_noise_jammed_output_sinr_linear(target_signal, 1.0, jsr),
            pfa,
        )
        for jsr in [0.0, 1.0, 10.0]
    ]

    assert pd_values == sorted(pd_values, reverse=True)


def test_pd_retention() -> None:
    """测试检测概率保持率。"""
    assert compute_pd_retention(clean_pd=0.8, jammed_pd=0.4) == pytest.approx(0.5)


def test_pd_retention_rejects_jammed_greater_than_clean() -> None:
    """测试 jammed Pd 大于 clean Pd 时会报错。"""
    with pytest.raises(JammingModelError):
        compute_pd_retention(clean_pd=0.8, jammed_pd=0.9)


def test_jamming_margin_reaches_target_pd() -> None:
    """测试抗干扰裕度代回后可达到目标 Pd。"""
    target_signal = np.ones(64, dtype=np.complex128)
    noise_variance = 1.0
    pfa = 1e-6
    target_pd = 0.9

    margin_jsr = compute_wideband_noise_jamming_margin_jsr_linear(
        target_signal,
        noise_variance,
        pfa,
        target_pd,
    )
    jammed_sinr = compute_wideband_noise_jammed_output_sinr_linear(
        target_signal,
        noise_variance,
        margin_jsr,
    )
    jammed_pd = compute_pd_square_law(jammed_sinr, pfa)

    assert margin_jsr > 0
    assert jammed_pd == pytest.approx(target_pd, abs=1e-6)


def test_jamming_margin_raises_when_clean_detection_insufficient() -> None:
    """测试无干扰检测性能不足时抗干扰裕度不可定义。"""
    target_signal = np.ones(4, dtype=np.complex128)

    with pytest.raises(JammingModelError):
        compute_wideband_noise_jamming_margin_jsr_linear(
            target_signal,
            noise_variance=10.0,
            pfa=1e-6,
            target_pd=0.9,
        )


def test_jamming_metrics_fields() -> None:
    """测试 JammingMetrics 字段和值合理。"""
    target_signal = np.ones(32, dtype=np.complex128)
    metrics = compute_wideband_noise_jamming_metrics(
        target_signal,
        noise_variance=1.0,
        pfa=1e-6,
        jsr_db=3.0,
        target_pd=0.8,
    )

    assert metrics.model_name == "wideband_complex_gaussian_noise_jamming"
    assert metrics.jammer_model == "complex_awgn_barrage"
    assert metrics.detector_model == "single_pulse_matched_filter_square_law_cawg"
    assert metrics.clean_pd >= metrics.jammed_pd
    assert metrics.pd_retention <= 1.0
    assert metrics.total_disturbance_variance == pytest.approx(
        metrics.noise_variance + metrics.jammer_variance,
    )
    assert metrics.jamming_margin_jsr_linear is not None
    assert metrics.jamming_margin_jsr_db is not None


def test_invalid_inputs_raise() -> None:
    """测试非法抗干扰模型输入会报错。"""
    valid_signal = np.ones(4, dtype=np.complex128)

    with pytest.raises(JammingModelError):
        compute_average_target_sample_power(np.array([], dtype=np.complex128))
    with pytest.raises(JammingModelError):
        compute_average_target_sample_power(np.zeros(4, dtype=np.complex128))
    with pytest.raises(JammingModelError):
        compute_average_target_sample_power(np.ones((2, 2), dtype=np.complex128))
    with pytest.raises(JammingModelError):
        compute_wideband_noise_jammed_output_sinr_linear(valid_signal, 0.0, 0.0)
    with pytest.raises(JammingModelError):
        compute_jammer_variance_from_jsr(valid_signal, jsr_linear=-1.0)
    with pytest.raises(JammingModelError):
        compute_wideband_noise_jamming_metrics(valid_signal, 1.0, pfa=0.0, jsr_db=0.0)
    with pytest.raises(JammingModelError):
        compute_wideband_noise_jamming_margin_jsr_linear(
            valid_signal,
            noise_variance=1.0,
            pfa=1e-3,
            target_pd=1e-4,
        )
