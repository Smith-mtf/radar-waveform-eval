"""距离、多普勒和速度分辨能力指标。"""

from __future__ import annotations

import math

from .schemas import ResolutionMetrics

SPEED_OF_LIGHT_MPS = 299_792_458.0
_CONSISTENCY_REL_TOL = 1e-9


class ResolutionMetricError(ValueError):
    """分辨能力指标输入错误或定义不一致。"""


def compute_range_resolution_m(
    bandwidth_hz: float,
    *,
    propagation_speed_mps: float = SPEED_OF_LIGHT_MPS,
) -> float:
    """计算距离分辨率 range_resolution_m = c / (2 * bandwidth_hz)。"""
    bandwidth = _validate_positive(bandwidth_hz, "bandwidth_hz")
    propagation_speed = _validate_positive(propagation_speed_mps, "propagation_speed_mps")
    return float(propagation_speed / (2.0 * bandwidth))


def compute_range_sample_spacing_m(
    sample_rate_hz: float,
    *,
    propagation_speed_mps: float = SPEED_OF_LIGHT_MPS,
) -> float:
    """计算距离采样间隔 range_sample_spacing_m = c / (2 * sample_rate_hz)。"""
    sample_rate = _validate_positive(sample_rate_hz, "sample_rate_hz")
    propagation_speed = _validate_positive(propagation_speed_mps, "propagation_speed_mps")
    return float(propagation_speed / (2.0 * sample_rate))


def compute_wavelength_m(
    carrier_frequency_hz: float,
    *,
    propagation_speed_mps: float = SPEED_OF_LIGHT_MPS,
) -> float:
    """计算波长 wavelength_m = c / carrier_frequency_hz。"""
    carrier_frequency = _validate_positive(carrier_frequency_hz, "carrier_frequency_hz")
    propagation_speed = _validate_positive(propagation_speed_mps, "propagation_speed_mps")
    return float(propagation_speed / carrier_frequency)


def compute_cpi_s(
    *,
    cpi_s: float | None = None,
    num_pulses: int | None = None,
    prf_hz: float | None = None,
    pri_s: float | None = None,
) -> float:
    """严格计算 CPI，不把 pulse_width_s 自动解释为 CPI。"""
    candidates: list[float] = []
    if cpi_s is not None:
        candidates.append(_validate_positive(cpi_s, "cpi_s"))

    if num_pulses is not None:
        validated_num_pulses = _validate_num_pulses(num_pulses)
        if prf_hz is not None:
            candidates.append(validated_num_pulses / _validate_positive(prf_hz, "prf_hz"))
        if pri_s is not None:
            candidates.append(validated_num_pulses * _validate_positive(pri_s, "pri_s"))
    elif prf_hz is not None or pri_s is not None:
        raise ResolutionMetricError("使用 prf_hz 或 pri_s 推导 CPI 时必须提供 num_pulses。")

    if prf_hz is not None and pri_s is not None:
        validated_prf_hz = _validate_positive(prf_hz, "prf_hz")
        validated_pri_s = _validate_positive(pri_s, "pri_s")
        if not math.isclose(
            validated_prf_hz,
            1.0 / validated_pri_s,
            rel_tol=_CONSISTENCY_REL_TOL,
            abs_tol=0.0,
        ):
            raise ResolutionMetricError("prf_hz 必须与 1 / pri_s 一致。")

    if not candidates:
        raise ResolutionMetricError("缺少 cpi_s 或 num_pulses + prf_hz/pri_s，无法定义 CPI。")

    reference = candidates[0]
    for candidate in candidates[1:]:
        if not math.isclose(reference, candidate, rel_tol=_CONSISTENCY_REL_TOL, abs_tol=0.0):
            raise ResolutionMetricError("直接给定的 cpi_s 与脉冲参数推导值不一致。")
    return float(reference)


def compute_doppler_resolution_hz(cpi_s: float) -> float:
    """计算多普勒分辨率 doppler_resolution_hz = 1 / cpi_s。"""
    cpi = _validate_positive(cpi_s, "cpi_s")
    return float(1.0 / cpi)


def compute_velocity_resolution_mps(wavelength_m: float, cpi_s: float) -> float:
    """计算速度分辨率 velocity_resolution_mps = wavelength_m / (2 * cpi_s)。"""
    wavelength = _validate_positive(wavelength_m, "wavelength_m")
    cpi = _validate_positive(cpi_s, "cpi_s")
    return float(wavelength / (2.0 * cpi))


def compute_resolution_metrics(
    *,
    bandwidth_hz: float,
    sample_rate_hz: float,
    carrier_frequency_hz: float | None = None,
    cpi_s: float | None = None,
    num_pulses: int | None = None,
    prf_hz: float | None = None,
    pri_s: float | None = None,
    propagation_speed_mps: float = SPEED_OF_LIGHT_MPS,
) -> ResolutionMetrics:
    """汇总严格定义的分辨能力指标；缺少 CPI 或载频时不猜测速度分辨率。"""
    wavelength_m = (
        None
        if carrier_frequency_hz is None
        else compute_wavelength_m(
            carrier_frequency_hz,
            propagation_speed_mps=propagation_speed_mps,
        )
    )
    computed_cpi_s: float | None = None
    doppler_resolution_hz: float | None = None
    velocity_resolution_mps: float | None = None
    if cpi_s is None and num_pulses is None and prf_hz is None and pri_s is None:
        computed_cpi_s = None
    else:
        computed_cpi_s = compute_cpi_s(
            cpi_s=cpi_s,
            num_pulses=num_pulses,
            prf_hz=prf_hz,
            pri_s=pri_s,
        )

    if computed_cpi_s is not None:
        doppler_resolution_hz = compute_doppler_resolution_hz(computed_cpi_s)
        if wavelength_m is not None:
            velocity_resolution_mps = compute_velocity_resolution_mps(wavelength_m, computed_cpi_s)

    return ResolutionMetrics(
        range_resolution_m=compute_range_resolution_m(
            bandwidth_hz,
            propagation_speed_mps=propagation_speed_mps,
        ),
        range_sample_spacing_m=compute_range_sample_spacing_m(
            sample_rate_hz,
            propagation_speed_mps=propagation_speed_mps,
        ),
        wavelength_m=wavelength_m,
        cpi_s=computed_cpi_s,
        doppler_resolution_hz=doppler_resolution_hz,
        velocity_resolution_mps=velocity_resolution_mps,
    )


def _validate_positive(value: float, name: str) -> float:
    """校验参数为有限正数。"""
    if not math.isfinite(value) or value <= 0:
        raise ResolutionMetricError(f"{name} 必须是有限正数。")
    return float(value)


def _validate_num_pulses(num_pulses: int) -> int:
    """校验脉冲数为正整数。"""
    if not isinstance(num_pulses, int) or num_pulses <= 0:
        raise ResolutionMetricError("num_pulses 必须是正整数。")
    return num_pulses
