"""波形生成测试。"""

from __future__ import annotations

import numpy as np

from radar_eval_core.engineering import compute_average_power
from radar_eval_core.schemas import WaveformConfig
from radar_eval_core.waveforms import generate_waveform


def test_rect_waveform_can_be_generated() -> None:
    """测试矩形脉冲波形可以生成。"""
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
    assert compute_average_power(signal.iq) > 0
    assert np.allclose(signal.iq, 2.0 + 0.0j)


def test_lfm_waveform_can_be_generated() -> None:
    """测试 LFM 波形可以生成，且相位不是常数。"""
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
    assert compute_average_power(signal.iq) > 0
    assert not np.allclose(phase, phase[0])


def test_phase_code_waveform_can_be_generated_with_two_phase_features() -> None:
    """测试二相相位编码波形可以生成，并包含两种符号特征。"""
    signal = generate_waveform(
        WaveformConfig(
            waveform_type="phase_code",
            sample_rate_hz=8e6,
            pulse_width_s=8e-6,
            phase_code=[1, 0, 1, 0],
        ),
    )

    unique_symbols = np.unique(np.round(signal.iq.real, decimals=8))

    assert len(signal.t) == len(signal.iq)
    assert signal.iq.dtype == np.complex128
    assert compute_average_power(signal.iq) > 0
    assert set(unique_symbols.tolist()) == {-1.0, 1.0}

