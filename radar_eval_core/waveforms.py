"""复基带波形生成接口。"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import numpy.typing as npt

from .schemas import WaveformConfig, WaveformSignal

_SAMPLE_COUNT_ATOL = 1e-9


def generate_waveform(config: WaveformConfig) -> WaveformSignal:
    """根据严格定义的波形配置生成复基带 IQ 信号。"""
    total_samples = _calculate_total_samples(config.sample_rate_hz, config.pulse_width_s)
    t = np.arange(total_samples, dtype=np.float64) / config.sample_rate_hz
    amplitude = math.sqrt(config.peak_power_w)
    metadata = _base_metadata(config, total_samples)

    if config.waveform_type == "rect":
        iq = np.full(total_samples, amplitude + 0.0j, dtype=np.complex128)
    elif config.waveform_type == "lfm":
        iq, lfm_metadata = _generate_lfm(config, t, amplitude)
        metadata.update(lfm_metadata)
    elif config.waveform_type == "phase_code":
        iq, phase_code_metadata = _generate_phase_code(config, total_samples, amplitude)
        metadata.update(phase_code_metadata)
    else:
        raise ValueError(f"不支持的波形类型: {config.waveform_type}")

    iq = iq.astype(np.complex128, copy=False)
    if len(t) != len(iq):
        raise ValueError("时间轴和 IQ 序列长度不一致。")

    return WaveformSignal(
        t=t,
        iq=iq,
        sample_rate_hz=config.sample_rate_hz,
        metadata=metadata,
    )


def build_waveform(config: WaveformConfig) -> WaveformSignal:
    """兼容旧入口，调用 :func:`generate_waveform` 生成复基带 IQ 信号。"""
    return generate_waveform(config)


def _calculate_total_samples(sample_rate_hz: float, pulse_width_s: float) -> int:
    """计算严格整数采样点数。"""
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz 必须大于 0。")
    if pulse_width_s <= 0:
        raise ValueError("pulse_width_s 必须大于 0。")

    raw_samples = sample_rate_hz * pulse_width_s
    rounded_samples = round(raw_samples)
    if not np.isclose(raw_samples, rounded_samples, rtol=0.0, atol=_SAMPLE_COUNT_ATOL):
        raise ValueError("sample_rate_hz * pulse_width_s 必须为整数采样点数。")

    total_samples = int(rounded_samples)
    if total_samples < 2:
        raise ValueError("total_samples 必须至少为 2。")

    return total_samples


def _base_metadata(config: WaveformConfig, total_samples: int) -> dict[str, Any]:
    """生成所有波形共享的 metadata。"""
    return {
        "name": config.name,
        "waveform_type": config.waveform_type,
        "carrier_frequency_hz": config.carrier_frequency_hz,
        "bandwidth_hz": config.bandwidth_hz,
        "pulse_width_s": config.pulse_width_s,
        "sample_rate_hz": config.sample_rate_hz,
        "peak_power_w": config.peak_power_w,
        "total_samples": total_samples,
    }


def _generate_lfm(
    config: WaveformConfig,
    t: npt.NDArray[np.float64],
    amplitude: float,
) -> tuple[npt.NDArray[np.complex128], dict[str, Any]]:
    """生成复基带 LFM 波形及其定义 metadata。"""
    chirp_rate_hz_per_s = config.bandwidth_hz / config.pulse_width_s
    t_centered = t - config.pulse_width_s / 2.0
    phase = math.pi * chirp_rate_hz_per_s * t_centered**2
    iq = (amplitude * np.exp(1j * phase)).astype(np.complex128)
    metadata = {
        "chirp_rate_hz_per_s": chirp_rate_hz_per_s,
        "start_frequency_hz_baseband": -config.bandwidth_hz / 2.0,
        "end_frequency_hz_baseband": config.bandwidth_hz / 2.0,
        "time_centered_definition": "t_centered = t - pulse_width_s / 2",
    }
    return iq, metadata


def _generate_phase_code(
    config: WaveformConfig,
    total_samples: int,
    amplitude: float,
) -> tuple[npt.NDArray[np.complex128], dict[str, Any]]:
    """生成二相相位编码复基带波形及其定义 metadata。"""
    code = _normalize_phase_code(config.phase_code)
    code_length = len(code)
    if total_samples % code_length != 0:
        raise ValueError("phase_code 波形要求 total_samples 能被 code_length 整除。")

    samples_per_chip = total_samples // code_length
    chip_duration_s = samples_per_chip / config.sample_rate_hz
    symbols = np.asarray(code, dtype=np.float64)
    iq = (amplitude * np.repeat(symbols, samples_per_chip)).astype(np.complex128)
    metadata = {
        "code_length": code_length,
        "samples_per_chip": samples_per_chip,
        "chip_duration_s": chip_duration_s,
    }
    return iq, metadata


def _normalize_phase_code(phase_code: list[int] | None) -> list[int]:
    """将 0/1 或 -1/1 相位码显式转换为 -1/1 符号。"""
    if phase_code is None:
        raise ValueError("phase_code 波形必须提供相位编码序列。")

    unique_values = set(phase_code)
    if unique_values == {0, 1}:
        return [-1 if value == 0 else 1 for value in phase_code]
    if unique_values == {-1, 1}:
        return list(phase_code)

    raise ValueError("phase_code 只允许使用完整的 0/1 或 -1/1 二相编码。")
