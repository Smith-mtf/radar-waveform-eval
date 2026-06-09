"""低截获波形暴露特征测试。"""

from __future__ import annotations

import numpy as np
import pytest

from radar_eval_core.lpi import (
    LpiFeatureError,
    compute_average_power_w,
    compute_duty_cycle,
    compute_lpi_exposure_metrics,
    compute_occupied_bandwidth,
    compute_papr_db,
    compute_peak_power_w,
    compute_two_sided_periodogram_psd,
)


def test_two_sided_periodogram_power_matches_time_domain_power() -> None:
    """测试双边 periodogram PSD 积分功率匹配时域平均功率。"""
    n = np.arange(128)
    signal = np.exp(1j * 2.0 * np.pi * 0.125 * n).astype(np.complex128)
    spectrum = compute_two_sided_periodogram_psd(signal, sample_rate_hz=1_000.0)

    assert spectrum.total_power_from_psd_w == pytest.approx(
        spectrum.average_power_time_domain_w,
        rel=1e-9,
        abs=1e-12,
    )
    assert spectrum.relative_power_error < 1e-9
    assert spectrum.method == "two_sided_periodogram"
    assert spectrum.window == "boxcar"
    assert spectrum.scaling == "density"
    assert spectrum.return_onesided is False


def test_periodogram_frequency_grid_properties() -> None:
    """测试 periodogram 频率网格属性。"""
    signal = np.ones(64, dtype=np.complex128)
    spectrum = compute_two_sided_periodogram_psd(signal, sample_rate_hz=2_000.0)

    assert len(spectrum.frequency_hz) == len(spectrum.psd_w_per_hz)
    assert spectrum.frequency_resolution_hz > 0
    assert np.all(np.diff(spectrum.frequency_hz) > 0)


def test_occupied_bandwidth_valid() -> None:
    """测试中心占用带宽返回正带宽和有序频率边界。"""
    signal = np.ones(128, dtype=np.complex128)
    sample_rate_hz = 1_000.0
    spectrum = compute_two_sided_periodogram_psd(signal, sample_rate_hz=sample_rate_hz)
    metrics = compute_occupied_bandwidth(spectrum, occupied_power_fraction=0.99)

    assert metrics.occupied_bandwidth_hz > 0
    assert metrics.lower_frequency_hz < metrics.upper_frequency_hz
    assert metrics.occupied_bandwidth_hz <= sample_rate_hz + 1e-12
    assert metrics.lower_tail_power_fraction == pytest.approx(0.005)
    assert metrics.upper_tail_power_fraction == pytest.approx(0.005)


def test_occupied_bandwidth_rejects_invalid_fraction() -> None:
    """测试中心占用功率比例非法时会报错。"""
    signal = np.ones(16, dtype=np.complex128)
    spectrum = compute_two_sided_periodogram_psd(signal, sample_rate_hz=1_000.0)

    with pytest.raises(LpiFeatureError):
        compute_occupied_bandwidth(spectrum, occupied_power_fraction=0.0)
    with pytest.raises(LpiFeatureError):
        compute_occupied_bandwidth(spectrum, occupied_power_fraction=1.0)


def test_duty_cycle_from_prf() -> None:
    """测试由 PRF 计算占空比。"""
    assert compute_duty_cycle(10e-6, prf_hz=1e3) == pytest.approx(0.01)


def test_duty_cycle_from_pri() -> None:
    """测试由 PRI 计算占空比。"""
    assert compute_duty_cycle(10e-6, pri_s=1e-3) == pytest.approx(0.01)


def test_duty_cycle_rejects_inconsistent_prf_pri() -> None:
    """测试 PRF 和 PRI 不一致时会报错。"""
    with pytest.raises(LpiFeatureError):
        compute_duty_cycle(10e-6, prf_hz=1e3, pri_s=2e-3)


def test_duty_cycle_rejects_greater_than_one() -> None:
    """测试占空比大于 1 时会报错。"""
    with pytest.raises(LpiFeatureError):
        compute_duty_cycle(2e-3, prf_hz=1e3)


def test_lpi_exposure_metrics_fields() -> None:
    """测试 LpiExposureMetrics 字段和值合理。"""
    signal = np.ones(128, dtype=np.complex128)
    metrics = compute_lpi_exposure_metrics(
        signal,
        sample_rate_hz=1_000.0,
        bandwidth_hz=100.0,
        pulse_width_s=10e-6,
        prf_hz=1e3,
    )

    assert metrics.model_name == "waveform_lpi_exposure_features"
    assert metrics.feature_scope == "waveform_features_only_no_intercept_receiver_model"
    assert metrics.peak_power_w >= metrics.average_power_w
    assert metrics.papr_db >= 0
    assert metrics.tbp > 0
    assert metrics.occupied_bandwidth_hz > 0
    assert metrics.nominal_avg_psd_w_per_hz > 0
    assert metrics.duty_cycle == pytest.approx(0.01)
    assert metrics.duty_cycle_definition == "pulse_width_s * prf_hz"


def test_lpi_metrics_do_not_include_intercept_probability() -> None:
    """测试 LPI 暴露特征不包含截获概率或截获距离字段。"""
    signal = np.ones(64, dtype=np.complex128)
    metrics = compute_lpi_exposure_metrics(
        signal,
        sample_rate_hz=1_000.0,
        bandwidth_hz=100.0,
        pulse_width_s=10e-6,
    )
    dumped_metrics = metrics.model_dump()

    assert "intercept_probability" not in dumped_metrics
    assert "intercept_range_ratio" not in dumped_metrics
    assert metrics.duty_cycle is None
    assert metrics.duty_cycle_definition is None


def test_invalid_inputs_raise() -> None:
    """测试非法 LPI 输入会报错。"""
    valid_signal = np.ones(16, dtype=np.complex128)

    with pytest.raises(LpiFeatureError):
        compute_peak_power_w(np.array([], dtype=np.complex128))
    with pytest.raises(LpiFeatureError):
        compute_average_power_w(np.zeros(4, dtype=np.complex128))
    with pytest.raises(LpiFeatureError):
        compute_papr_db(np.ones((2, 2), dtype=np.complex128))
    with pytest.raises(LpiFeatureError):
        compute_two_sided_periodogram_psd(valid_signal, sample_rate_hz=0.0)
    with pytest.raises(LpiFeatureError):
        compute_lpi_exposure_metrics(
            valid_signal,
            sample_rate_hz=1_000.0,
            bandwidth_hz=0.0,
            pulse_width_s=10e-6,
        )
    with pytest.raises(LpiFeatureError):
        compute_lpi_exposure_metrics(
            valid_signal,
            sample_rate_hz=1_000.0,
            bandwidth_hz=100.0,
            pulse_width_s=0.0,
        )
