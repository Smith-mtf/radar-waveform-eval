"""波形生成相关接口。"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from .schemas import WaveformConfig, WaveformSignal


def generate_waveform(config: WaveformConfig) -> WaveformSignal:
    """根据波形配置生成复基带 IQ 信号。"""
    n_samples = _calculate_sample_count(config.sample_rate_hz, config.pulse_width_s)
    t = np.arange(n_samples, dtype=np.float64) / config.sample_rate_hz
    amplitude = math.sqrt(config.peak_power_w)

    if config.waveform_type == "rect":
        iq = np.full(n_samples, amplitude, dtype=np.complex128)
    elif config.waveform_type == "lfm":
        iq = _generate_lfm(config, t, amplitude)
    elif config.waveform_type == "phase_code":
        iq = _generate_phase_code(config, t, amplitude)
    else:
        raise ValueError(f"不支持的波形类型: {config.waveform_type}")

    return WaveformSignal(
        t=t,
        iq=iq.astype(np.complex128, copy=False),
        sample_rate_hz=config.sample_rate_hz,
        metadata={
            "name": config.name,
            "waveform_type": config.waveform_type,
            "carrier_frequency_hz": config.carrier_frequency_hz,
            "bandwidth_hz": config.bandwidth_hz,
            "pulse_width_s": config.pulse_width_s,
            "peak_power_w": config.peak_power_w,
        },
    )


def build_waveform(config: WaveformConfig) -> WaveformSignal:
    """兼容旧入口，调用 :func:`generate_waveform` 生成复基带 IQ 信号。"""
    return generate_waveform(config)


def _calculate_sample_count(sample_rate_hz: float, pulse_width_s: float) -> int:
    """计算脉冲采样点数。"""
    n_samples = int(round(sample_rate_hz * pulse_width_s))
    if n_samples < 1:
        raise ValueError("采样率和脉宽组合至少需要生成 1 个采样点。")
    return n_samples


def _generate_lfm(
    config: WaveformConfig,
    t: npt.NDArray[np.float64],
    amplitude: float,
) -> npt.NDArray[np.complex128]:
    """生成线性调频复基带波形。"""
    chirp_rate_hz_per_s = config.bandwidth_hz / config.pulse_width_s
    t_centered = t - config.pulse_width_s / 2.0
    phase = math.pi * chirp_rate_hz_per_s * t_centered**2
    return (amplitude * np.exp(1j * phase)).astype(np.complex128)


def _generate_phase_code(
    config: WaveformConfig,
    t: npt.NDArray[np.float64],
    amplitude: float,
) -> npt.NDArray[np.complex128]:
    """生成二相相位编码复基带波形。"""
    code = _normalize_phase_code(config.phase_code)
    chip_width_s = config.pulse_width_s / len(code)
    chip_index = np.floor(t / chip_width_s).astype(np.int64)
    chip_index = np.clip(chip_index, 0, len(code) - 1)
    symbols = np.asarray(code, dtype=np.float64)[chip_index]
    return (amplitude * symbols).astype(np.complex128)


def _normalize_phase_code(phase_code: list[int] | None) -> list[int]:
    """将 0/1 或 -1/1 相位码统一为 -1/1 符号。"""
    if not phase_code:
        raise ValueError("phase_code 波形必须提供非空相位编码序列。")

    unique_values = set(phase_code)
    if unique_values <= {0, 1}:
        return [-1 if value == 0 else 1 for value in phase_code]
    if unique_values <= {-1, 1}:
        return phase_code

    raise ValueError("phase_code 只允许使用 0/1 或 -1/1 编码。")
