"""匹配滤波和零多普勒旁瓣指标测试。"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radar_eval_core.matched_filter import (
    MainlobeDetectionError,
    MatchedFilterError,
    autocorrelation_matched_filter,
    compute_zero_doppler_islr_db,
    compute_zero_doppler_pslr_db,
    compute_zero_doppler_sidelobe_metrics,
    find_mainlobe_bounds,
    matched_filter,
)
from radar_eval_core.schemas import MainlobeSpec


def test_matched_filter_returns_complex_array() -> None:
    """测试匹配滤波返回复数数组，且长度满足线性卷积定义。"""
    rx = np.array([1 + 1j, 2 - 1j], dtype=np.complex128)
    tx = np.array([1 - 1j, -1 + 0j, 2 + 0j], dtype=np.complex128)

    output = matched_filter(rx, tx)

    assert np.issubdtype(output.dtype, np.complexfloating)
    assert output.dtype == np.complex128
    assert len(output) == len(rx) + len(tx) - 1


def test_autocorrelation_peak_at_expected_index() -> None:
    """测试自匹配滤波主峰索引位于 len(tx) - 1。"""
    tx = np.array([1 + 0j, 2 + 0j, -1 + 0j], dtype=np.complex128)
    pc = autocorrelation_matched_filter(tx)

    assert int(np.argmax(np.abs(pc))) == len(tx) - 1


def test_barker_code_zero_doppler_pslr() -> None:
    """测试 Barker 7 码零多普勒 PSLR。"""
    tx = np.array([1, 1, 1, -1, -1, 1, -1], dtype=np.complex128)
    spec = MainlobeSpec(method="manual_guard_samples", guard_samples=0)
    pc = autocorrelation_matched_filter(tx)

    assert np.max(np.abs(pc)) == pytest.approx(7.0)
    assert compute_zero_doppler_pslr_db(pc, spec) == pytest.approx(20.0 * math.log10(1.0 / 7.0))


def test_barker_code_zero_doppler_islr() -> None:
    """测试 Barker 7 码零多普勒 ISLR 为有限负值。"""
    tx = np.array([1, 1, 1, -1, -1, 1, -1], dtype=np.complex128)
    spec = MainlobeSpec(method="manual_guard_samples", guard_samples=0)
    islr_db = compute_zero_doppler_islr_db(autocorrelation_matched_filter(tx), spec)

    assert math.isfinite(islr_db)
    assert islr_db < 0


def test_mainlobe_manual_guard_requires_guard() -> None:
    """测试手动主瓣保护区必须显式提供 guard_samples。"""
    with pytest.raises(ValueError):
        MainlobeSpec(method="manual_guard_samples")


def test_first_local_minimum_no_hidden_fallback() -> None:
    """测试 first_local_minimum 找不到双侧极小值时不会隐藏兜底。"""
    magnitude = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
    spec = MainlobeSpec(method="first_local_minimum")

    with pytest.raises(MainlobeDetectionError):
        find_mainlobe_bounds(magnitude, peak_index=2, spec=spec)


def test_null_to_null_no_hidden_fallback() -> None:
    """测试 null_to_null 找不到双侧零点时不会隐藏兜底。"""
    magnitude = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
    spec = MainlobeSpec(method="null_to_null", null_tolerance=1e-6)

    with pytest.raises(MainlobeDetectionError):
        find_mainlobe_bounds(magnitude, peak_index=2, spec=spec)


def test_no_sidelobe_region_returns_negative_infinity() -> None:
    """测试主瓣覆盖全部采样点时 PSLR 和 ISLR 返回 -inf。"""
    pc = np.array([1.0 + 0j, 2.0 + 0j, 1.0 + 0j], dtype=np.complex128)
    spec = MainlobeSpec(method="manual_guard_samples", guard_samples=1)

    assert compute_zero_doppler_pslr_db(pc, spec) == -math.inf
    assert compute_zero_doppler_islr_db(pc, spec) == -math.inf


def test_invalid_matched_filter_inputs_raise() -> None:
    """测试匹配滤波拒绝空数组、全零数组和非一维数组。"""
    valid = np.array([1 + 0j], dtype=np.complex128)

    with pytest.raises(MatchedFilterError):
        matched_filter(np.array([], dtype=np.complex128), valid)
    with pytest.raises(MatchedFilterError):
        matched_filter(np.zeros(2, dtype=np.complex128), valid)
    with pytest.raises(MatchedFilterError):
        matched_filter(np.ones((2, 2), dtype=np.complex128), valid)


def test_invalid_mainlobe_and_pc_inputs_raise() -> None:
    """测试主瓣检测和旁瓣指标拒绝非法输入。"""
    spec = MainlobeSpec(method="manual_guard_samples", guard_samples=0)

    with pytest.raises(ValueError):
        compute_zero_doppler_pslr_db(np.array([], dtype=np.complex128), spec)
    with pytest.raises(ValueError):
        compute_zero_doppler_islr_db(np.zeros(3, dtype=np.complex128), spec)
    with pytest.raises(ValueError):
        compute_zero_doppler_pslr_db(np.ones((2, 2), dtype=np.complex128), spec)
    with pytest.raises(MainlobeDetectionError):
        find_mainlobe_bounds(np.array([0.0, 1.0, 0.0]), peak_index=3, spec=spec)


def test_zero_doppler_sidelobe_metrics_returns_structured_result() -> None:
    """测试零多普勒旁瓣指标返回结构化结果。"""
    tx = np.array([1, 1, 1, -1, -1, 1, -1], dtype=np.complex128)
    spec = MainlobeSpec(method="manual_guard_samples", guard_samples=0)

    metrics = compute_zero_doppler_sidelobe_metrics(tx, spec)

    assert metrics.peak_index == len(tx) - 1
    assert metrics.peak_magnitude == pytest.approx(7.0)
    assert metrics.mainlobe_width_samples == 1
    assert metrics.zero_doppler_pslr_db <= 0
    assert metrics.zero_doppler_islr_db < 0
