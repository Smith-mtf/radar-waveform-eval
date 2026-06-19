"""波形生成测试。"""

from __future__ import annotations

import numpy as np
import pytest

from radar_eval_core.engineering import compute_average_power
from radar_eval_core.schemas import WaveformConfig
from radar_eval_core.waveforms import generate_waveform


def test_rect_waveform_power_matches_peak_power() -> None:
    """测试矩形脉冲波形功率定义。"""
    signal = generate_waveform(
        WaveformConfig(
            waveform_type="rect",
            sample_rate_hz=10e6,
            pulse_width_s=10e-6,
            peak_power_w=4.0,
        ),
    )

    assert len(signal.t) == len(signal.iq)
    assert signal.iq.dtype == np.complex128
    assert compute_average_power(signal.iq) == pytest.approx(4.0)
    assert np.allclose(signal.iq, 2.0 + 0.0j)
    assert signal.metadata["bandwidth_hz"] == pytest.approx(100_000.0)
    assert signal.metadata["bandwidth_definition"] == "rect_derived_1_over_pulse_width"


def test_lfm_waveform_metadata_and_phase_definition() -> None:
    """测试 LFM 波形 metadata 和相位变化。"""
    signal = generate_waveform(
        WaveformConfig(
            waveform_type="lfm",
            bandwidth_hz=2e6,
            sample_rate_hz=20e6,
            pulse_width_s=20e-6,
        ),
    )

    phase = np.unwrap(np.angle(signal.iq))

    assert len(signal.t) == len(signal.iq)
    assert signal.iq.dtype == np.complex128
    assert not np.allclose(phase, phase[0])
    assert signal.metadata["chirp_rate_hz_per_s"] == pytest.approx(1e11)
    assert signal.metadata["start_frequency_hz_baseband"] == pytest.approx(-1e6)
    assert signal.metadata["end_frequency_hz_baseband"] == pytest.approx(1e6)
    assert signal.metadata["bandwidth_hz"] == pytest.approx(2e6)
    assert signal.metadata["bandwidth_definition"] == "explicit_lfm_sweep_bandwidth"
    assert "time_centered_definition" in signal.metadata


def test_phase_code_waveform_accepts_pm_one_code() -> None:
    """测试 phase_code 支持 -1/1 输入。"""
    signal = generate_waveform(
        WaveformConfig(
            waveform_type="phase_code",
            sample_rate_hz=8e6,
            pulse_width_s=2e-6,
            peak_power_w=1.0,
            phase_code=[1, -1, 1, -1],
        ),
    )

    unique_symbols = np.unique(np.round(signal.iq.real, decimals=8))

    assert signal.iq.dtype == np.complex128
    assert set(unique_symbols.tolist()) == {-1.0, 1.0}
    assert signal.metadata["code_length"] == 4
    assert signal.metadata["samples_per_chip"] == 16
    assert signal.metadata["chip_duration_s"] == pytest.approx(2e-6)
    assert signal.metadata["chip_rate_hz"] == pytest.approx(500_000.0)
    assert signal.metadata["bandwidth_hz"] == pytest.approx(500_000.0)
    assert signal.metadata["bandwidth_definition"] == "phase_code_derived_code_rate"
    assert signal.metadata["subpulse_width_s"] == pytest.approx(2e-6)
    assert signal.metadata["pulse_width_s"] == pytest.approx(8e-6)
    assert signal.metadata["pulse_width_definition"] == "phase_code_total_code_duration"


def test_phase_code_waveform_accepts_zero_one_code() -> None:
    """测试 phase_code 支持 0/1 输入并显式转换为 -1/1。"""
    signal = generate_waveform(
        WaveformConfig(
            waveform_type="phase_code",
            sample_rate_hz=8e6,
            pulse_width_s=2e-6,
            peak_power_w=1.0,
            phase_code=[1, 0, 1, 0],
        ),
    )

    unique_symbols = np.unique(np.round(signal.iq.real, decimals=8))

    assert len(signal.t) == len(signal.iq)
    assert set(unique_symbols.tolist()) == {-1.0, 1.0}
    assert compute_average_power(signal.iq) == pytest.approx(1.0)


def test_phase_code_rejects_invalid_code_values() -> None:
    """测试非法 phase_code 取值会被拒绝。"""
    with pytest.raises(ValueError):
        WaveformConfig(waveform_type="phase_code", phase_code=[1, 2])


def test_phase_code_rejects_non_integer_subpulse_sample_count() -> None:
    """测试 phase_code 子脉冲宽度不是整数采样点时报错。"""
    config = WaveformConfig(
        waveform_type="phase_code",
        sample_rate_hz=10e6,
        pulse_width_s=0.15e-6,
        phase_code=[1, -1, 1],
    )

    with pytest.raises(ValueError):
        generate_waveform(config)


def test_waveform_rejects_non_integer_sample_count() -> None:
    """测试非整数采样点配置会被拒绝。"""
    config = WaveformConfig(
        waveform_type="rect",
        sample_rate_hz=10.0,
        pulse_width_s=0.25,
    )

    with pytest.raises(ValueError):
        generate_waveform(config)


def test_waveform_rejects_less_than_two_total_samples() -> None:
    """测试总采样点少于 2 的配置会被拒绝。"""
    config = WaveformConfig(
        waveform_type="rect",
        sample_rate_hz=10.0,
        pulse_width_s=0.1,
    )

    with pytest.raises(ValueError):
        generate_waveform(config)
