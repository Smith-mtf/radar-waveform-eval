"""分辨能力指标测试。"""

from __future__ import annotations

import pytest

from radar_eval_core.resolution import (
    SPEED_OF_LIGHT_MPS,
    ResolutionMetricError,
    compute_cpi_s,
    compute_doppler_resolution_hz,
    compute_range_resolution_m,
    compute_range_sample_spacing_m,
    compute_resolution_metrics,
    compute_velocity_resolution_mps,
    compute_wavelength_m,
)


def test_range_resolution() -> None:
    """测试距离分辨率公式。"""
    assert compute_range_resolution_m(20e6) == pytest.approx(SPEED_OF_LIGHT_MPS / (2 * 20e6))


def test_range_sample_spacing() -> None:
    """测试距离采样间隔公式。"""
    assert compute_range_sample_spacing_m(100e6) == pytest.approx(SPEED_OF_LIGHT_MPS / (2 * 100e6))


def test_wavelength() -> None:
    """测试波长公式。"""
    assert compute_wavelength_m(10e9) == pytest.approx(SPEED_OF_LIGHT_MPS / 10e9)


def test_cpi_direct_input() -> None:
    """测试直接输入 CPI。"""
    assert compute_cpi_s(cpi_s=0.064) == pytest.approx(0.064)


def test_cpi_from_num_pulses_and_prf() -> None:
    """测试由脉冲数和 PRF 推导 CPI。"""
    assert compute_cpi_s(num_pulses=64, prf_hz=1000.0) == pytest.approx(0.064)


def test_cpi_from_num_pulses_and_pri() -> None:
    """测试由脉冲数和 PRI 推导 CPI。"""
    assert compute_cpi_s(num_pulses=64, pri_s=0.001) == pytest.approx(0.064)


def test_cpi_rejects_inconsistent_prf_pri() -> None:
    """测试 PRF 和 PRI 不一致时报错。"""
    with pytest.raises(ResolutionMetricError):
        compute_cpi_s(num_pulses=64, prf_hz=1000.0, pri_s=0.002)


def test_cpi_rejects_inconsistent_direct_and_derived_value() -> None:
    """测试直接 CPI 与推导 CPI 不一致时报错。"""
    with pytest.raises(ResolutionMetricError):
        compute_cpi_s(cpi_s=0.1, num_pulses=64, prf_hz=1000.0)


def test_doppler_and_velocity_resolution() -> None:
    """测试多普勒和速度分辨率公式。"""
    wavelength = compute_wavelength_m(10e9)

    assert compute_doppler_resolution_hz(0.064) == pytest.approx(1.0 / 0.064)
    assert compute_velocity_resolution_mps(wavelength, 0.064) == pytest.approx(
        wavelength / (2 * 0.064),
    )


def test_missing_cpi_marks_doppler_and_velocity_resolution_unavailable() -> None:
    """测试缺少 CPI 参数时相关指标为 None。"""
    metrics = compute_resolution_metrics(
        bandwidth_hz=20e6,
        sample_rate_hz=100e6,
        carrier_frequency_hz=10e9,
    )

    assert metrics.cpi_s is None
    assert metrics.doppler_resolution_hz is None
    assert metrics.velocity_resolution_mps is None
