"""工程指标测试。"""

from __future__ import annotations

import numpy as np
import pytest

from radar_eval_core.engineering import (
    compute_average_power,
    compute_nominal_avg_psd_w_per_hz,
    compute_papr_db,
    compute_peak_power,
    compute_tbp,
)


def test_compute_average_power_for_constant_amplitude_signal() -> None:
    """测试恒幅信号平均功率。"""
    iq = np.full(16, 2.0 + 0.0j, dtype=np.complex128)

    assert compute_average_power(iq) == pytest.approx(4.0)


def test_compute_peak_power_for_constant_amplitude_signal() -> None:
    """测试恒幅信号峰值功率。"""
    iq = np.full(16, 3.0 + 0.0j, dtype=np.complex128)

    assert compute_peak_power(iq) == pytest.approx(9.0)


def test_constant_amplitude_signal_papr_is_zero_db() -> None:
    """测试恒幅信号 PAPR 接近 0 dB。"""
    iq = np.full(16, 2.0 + 0.0j, dtype=np.complex128)

    assert compute_papr_db(iq) == pytest.approx(0.0)


def test_compute_tbp_equals_bandwidth_times_pulse_width() -> None:
    """测试时间带宽积公式。"""
    assert compute_tbp(20e6, 20e-6) == pytest.approx(400.0)


def test_nominal_avg_psd_decreases_when_bandwidth_increases() -> None:
    """测试平均功率不变时带宽越大，名义平均 PSD 越小。"""
    narrow_band_psd = compute_nominal_avg_psd_w_per_hz(10.0, 1e6)
    wide_band_psd = compute_nominal_avg_psd_w_per_hz(10.0, 10e6)

    assert wide_band_psd < narrow_band_psd


def test_engineering_metrics_reject_empty_signal() -> None:
    """测试工程指标拒绝空数组。"""
    with pytest.raises(ValueError):
        compute_average_power(np.array([], dtype=np.complex128))


def test_engineering_metrics_reject_non_1d_signal() -> None:
    """测试工程指标拒绝非一维数组。"""
    with pytest.raises(ValueError):
        compute_peak_power(np.ones((2, 2), dtype=np.complex128))


def test_papr_rejects_zero_power_signal() -> None:
    """测试 PAPR 拒绝零功率信号。"""
    with pytest.raises(ValueError):
        compute_papr_db(np.zeros(4, dtype=np.complex128))


def test_tbp_rejects_invalid_inputs() -> None:
    """测试 TBP 拒绝非法带宽和脉宽。"""
    with pytest.raises(ValueError):
        compute_tbp(0.0, 1e-6)
    with pytest.raises(ValueError):
        compute_tbp(1e6, 0.0)


def test_nominal_avg_psd_rejects_invalid_inputs() -> None:
    """测试名义平均 PSD 拒绝负平均功率和非法带宽。"""
    with pytest.raises(ValueError):
        compute_nominal_avg_psd_w_per_hz(-1.0, 1e6)
    with pytest.raises(ValueError):
        compute_nominal_avg_psd_w_per_hz(1.0, 0.0)
