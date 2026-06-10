"""数据结构测试。"""

from __future__ import annotations

import pytest

from radar_eval_core.schemas import EvaluationRequest, WaveformConfig, derive_nominal_bandwidth_hz


def test_create_minimal_evaluation_request() -> None:
    """测试可以创建最小评估请求。"""
    request = EvaluationRequest()

    assert request.waveform.name == "default_waveform"
    assert request.scenario.name == "default_scenario"
    assert request.jammer.enabled is False


def test_invalid_waveform_type_is_rejected() -> None:
    """测试非法波形类型会被拒绝。"""
    with pytest.raises(ValueError):
        WaveformConfig(waveform_type="hopping")


def test_phase_code_waveform_requires_code() -> None:
    """测试 phase_code 波形必须提供相位编码。"""
    with pytest.raises(ValueError):
        WaveformConfig(waveform_type="phase_code")


def test_phase_code_waveform_rejects_short_code() -> None:
    """测试 phase_code 长度必须至少为 2。"""
    with pytest.raises(ValueError):
        WaveformConfig(waveform_type="phase_code", phase_code=[1])


def test_phase_code_waveform_rejects_invalid_values() -> None:
    """测试 phase_code 只允许完整的 0/1 或 -1/1 二相编码。"""
    with pytest.raises(ValueError):
        WaveformConfig(waveform_type="phase_code", phase_code=[1, 2])


def test_non_phase_code_waveform_rejects_phase_code() -> None:
    """测试非 phase_code 波形不接受 phase_code。"""
    with pytest.raises(ValueError):
        WaveformConfig(waveform_type="rect", phase_code=[1, -1])


def test_rect_waveform_derives_nominal_bandwidth_from_pulse_width() -> None:
    """测试 rect 波形按脉宽派生名义带宽。"""
    config = WaveformConfig(
        waveform_type="rect",
        bandwidth_hz=20e6,
        pulse_width_s=50e-6,
    )

    assert config.bandwidth_hz == pytest.approx(20_000.0)


def test_phase_code_waveform_derives_nominal_bandwidth_from_code_rate() -> None:
    """测试 phase_code 波形按码片率派生名义带宽。"""
    config = WaveformConfig(
        waveform_type="phase_code",
        bandwidth_hz=20e6,
        pulse_width_s=50e-6,
        phase_code=[1, 1, 1, -1, -1, 1, -1, 1, -1, 1],
    )

    assert config.bandwidth_hz == pytest.approx(200_000.0)
    assert derive_nominal_bandwidth_hz(
        "phase_code",
        50e-6,
        phase_code=[1, -1],
    ) == pytest.approx(40_000.0)


def test_lfm_waveform_preserves_explicit_bandwidth() -> None:
    """测试 lfm 波形保留显式扫频带宽。"""
    config = WaveformConfig(waveform_type="lfm", bandwidth_hz=2e6)

    assert config.bandwidth_hz == pytest.approx(2e6)


def test_waveform_config_rejects_non_positive_bandwidth() -> None:
    """测试带宽必须大于 0。"""
    with pytest.raises(ValueError):
        WaveformConfig(bandwidth_hz=0.0)


def test_waveform_config_rejects_non_positive_pulse_width() -> None:
    """测试脉宽必须大于 0。"""
    with pytest.raises(ValueError):
        WaveformConfig(pulse_width_s=0.0)


def test_waveform_config_rejects_non_positive_sample_rate() -> None:
    """测试采样率必须大于 0。"""
    with pytest.raises(ValueError):
        WaveformConfig(sample_rate_hz=0.0)


def test_waveform_config_rejects_non_positive_peak_power() -> None:
    """测试峰值功率必须大于 0。"""
    with pytest.raises(ValueError):
        WaveformConfig(peak_power_w=0.0)
