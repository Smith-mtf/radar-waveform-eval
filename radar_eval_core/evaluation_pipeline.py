"""完整算法评估流水线。"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .ambiguity import (
    AmbiguityFunctionError,
    DopplerToleranceError,
    compute_ambiguity_function,
    compute_doppler_tolerance,
    get_zero_delay_doppler_cut,
)
from .detection import DetectionModelError, compute_detection_metrics
from .engineering import (
    compute_average_power,
    compute_papr_db,
    compute_peak_power,
    compute_tbp,
)
from .jamming import (
    JammingModelError,
    compute_wideband_noise_jamming_margin_jsr_db,
    compute_wideband_noise_jamming_margin_jsr_linear,
    compute_wideband_noise_jamming_metrics,
)
from .lpi import LpiFeatureError, compute_lpi_exposure_metrics, compute_two_sided_periodogram_psd
from .matched_filter import (
    MainlobeDetectionError,
    MatchedFilterError,
    autocorrelation_matched_filter,
    compute_zero_doppler_sidelobe_metrics,
)
from .resolution import ResolutionMetricError, compute_resolution_metrics
from .schemas import EvaluationRequest, EvaluationResult, RawMetric
from .scoring import ScoringConfig, ScoringError, compute_axis_scores, compute_total_score
from .waveforms import generate_waveform

AMBIGUITY_HEATMAP_DELAY_SPAN_SAMPLES = 256
AMBIGUITY_HEATMAP_DELAY_POINTS = 129
AMBIGUITY_HEATMAP_DOPPLER_POINTS = 81


class EvaluationPipelineError(ValueError):
    """完整评估流水线配置错误或必须指标计算失败。"""


def compute_waveform_evaluation(
    request: EvaluationRequest,
    scoring_config: ScoringConfig,
) -> EvaluationResult:
    """执行完整算法评估并返回结构化结果。"""
    try:
        waveform_signal = generate_waveform(request.waveform)
        raw_metrics: list[RawMetric] = []
        raw_metrics.extend(_compute_engineering_raw_metrics(request, waveform_signal.iq))
        raw_metrics.extend(_compute_resolution_raw_metrics(request))
        raw_metrics.extend(_compute_sidelobe_raw_metrics(request, waveform_signal.iq))
        ambiguity_chart_data, doppler_tolerance_metric = _compute_ambiguity_outputs(
            request,
            waveform_signal.iq,
        )
        raw_metrics.append(doppler_tolerance_metric)
        raw_metrics.extend(_compute_detection_raw_metrics(request, waveform_signal.iq))
        raw_metrics.extend(_compute_jamming_raw_metrics(request, waveform_signal.iq))
        raw_metrics.extend(_compute_lpi_raw_metrics(request, waveform_signal.iq))

        axis_scores = compute_axis_scores(raw_metrics, scoring_config)
        overall_score = compute_total_score(axis_scores, scoring_config)
    except (
        ValueError,
        DetectionModelError,
        JammingModelError,
        LpiFeatureError,
        MatchedFilterError,
        MainlobeDetectionError,
        AmbiguityFunctionError,
        ResolutionMetricError,
        ScoringError,
    ) as exc:
        raise EvaluationPipelineError(str(exc)) from exc

    chart_data = {
        "waveform_preview": _compute_waveform_preview_chart(request, waveform_signal),
        "zero_doppler_cut": _compute_zero_doppler_chart(waveform_signal.iq),
        "zero_delay_doppler_cut": ambiguity_chart_data,
        "ambiguity_heatmap": _compute_ambiguity_heatmap_chart(request, waveform_signal.iq),
        "spectrum_psd": _compute_spectrum_chart(request, waveform_signal.iq),
    }
    return EvaluationResult(
        request=request,
        overall_score=overall_score,
        axis_scores=axis_scores,
        raw_metrics=raw_metrics,
        chart_data=chart_data,
        summary="算法核心闭环评估完成；评分依赖 scoring_config 的归一化边界和权重。",
    )


def _compute_engineering_raw_metrics(request: EvaluationRequest, iq: np.ndarray) -> list[RawMetric]:
    """计算工程基础指标。"""
    average_power = compute_average_power(iq)
    peak_power = compute_peak_power(iq)
    papr = compute_papr_db(iq)
    tbp = compute_tbp(request.waveform.bandwidth_hz, request.waveform.pulse_width_s)
    return [
        _available_metric(
            "engineering.average_power_w",
            "engineering",
            average_power,
            "W",
            "平均功率",
        ),
        _available_metric(
            "engineering.peak_power_w",
            "engineering",
            peak_power,
            "W",
            "峰值功率",
        ),
        _available_metric("engineering.papr_db", "engineering", papr, "dB", "PAPR"),
        _available_metric("engineering.tbp", "engineering", tbp, "", "时宽带宽积"),
    ]


def _compute_resolution_raw_metrics(request: EvaluationRequest) -> list[RawMetric]:
    """计算分辨能力原始指标。"""
    settings = request.evaluation
    resolution_metrics = compute_resolution_metrics(
        bandwidth_hz=request.waveform.bandwidth_hz,
        sample_rate_hz=request.waveform.sample_rate_hz,
        carrier_frequency_hz=request.waveform.carrier_frequency_hz,
        cpi_s=settings.cpi_s,
        num_pulses=settings.num_pulses,
        prf_hz=settings.prf_hz,
        pri_s=settings.pri_s,
    )
    metrics = [
        _available_metric(
            "resolution.range_resolution_m",
            "resolution",
            resolution_metrics.range_resolution_m,
            "m",
            "距离分辨率",
        ),
        _available_metric(
            "resolution.range_sample_spacing_m",
            "resolution",
            resolution_metrics.range_sample_spacing_m,
            "m",
            "距离采样间隔",
        ),
    ]
    metrics.append(
        _metric_or_unavailable(
            "resolution.wavelength_m",
            "resolution",
            resolution_metrics.wavelength_m,
            "m",
            "缺少 carrier_frequency_hz，无法计算波长。",
            "波长",
        ),
    )
    metrics.append(
        _metric_or_unavailable(
            "resolution.cpi_s",
            "resolution",
            resolution_metrics.cpi_s,
            "s",
            "缺少 cpi_s 或 num_pulses + prf_hz/pri_s，无法定义 CPI。",
            "相干处理时间",
        ),
    )
    metrics.append(
        _metric_or_unavailable(
            "resolution.doppler_resolution_hz",
            "resolution",
            resolution_metrics.doppler_resolution_hz,
            "Hz",
            "缺少 CPI，无法计算多普勒分辨率。",
            "多普勒分辨率",
        ),
    )
    metrics.append(
        _metric_or_unavailable(
            "resolution.velocity_resolution_mps",
            "resolution",
            resolution_metrics.velocity_resolution_mps,
            "m/s",
            "缺少 CPI 或 carrier_frequency_hz，无法计算速度分辨率。",
            "速度分辨率",
        ),
    )
    return metrics


def _compute_sidelobe_raw_metrics(request: EvaluationRequest, iq: np.ndarray) -> list[RawMetric]:
    """计算零多普勒旁瓣指标。"""
    metrics = compute_zero_doppler_sidelobe_metrics(iq, request.evaluation.mainlobe_spec)
    return [
        _available_metric(
            "sidelobe_ambiguity.zero_doppler_pslr_db",
            "sidelobe_ambiguity",
            metrics.zero_doppler_pslr_db,
            "dB",
            "零多普勒 PSLR",
        ),
        _available_metric(
            "sidelobe_ambiguity.zero_doppler_islr_db",
            "sidelobe_ambiguity",
            metrics.zero_doppler_islr_db,
            "dB",
            "零多普勒 ISLR",
        ),
        _available_metric(
            "sidelobe_ambiguity.mainlobe_width_samples",
            "sidelobe_ambiguity",
            metrics.mainlobe_width_samples,
            "samples",
            "主瓣宽度",
        ),
    ]


def _compute_ambiguity_outputs(
    request: EvaluationRequest,
    iq: np.ndarray,
) -> tuple[dict[str, Any], RawMetric]:
    """计算 zero-delay Doppler cut 和多普勒容忍性。"""
    doppler_hz = _build_doppler_grid(request)
    result = compute_ambiguity_function(
        iq,
        sample_rate_hz=request.waveform.sample_rate_hz,
        doppler_hz=doppler_hz,
        delay_samples=np.array([0], dtype=int),
    )
    cut_doppler_hz, zero_delay_cut = get_zero_delay_doppler_cut(result)
    chart_data = _series_for_chart(
        cut_doppler_hz,
        zero_delay_cut,
        x_key="doppler_hz",
        y_key="magnitude_normalized",
    )
    try:
        doppler_tolerance = compute_doppler_tolerance(result, request.evaluation.doppler_loss_db)
    except DopplerToleranceError as exc:
        return chart_data, _unavailable_metric(
            "sidelobe_ambiguity.doppler_tolerance_hz",
            "sidelobe_ambiguity",
            str(exc),
        )
    return chart_data, _available_metric(
        "sidelobe_ambiguity.doppler_tolerance_hz",
        "sidelobe_ambiguity",
        doppler_tolerance.doppler_tolerance_hz,
        "Hz",
        "基于 zero-delay Doppler cut 的多普勒容忍性",
    )


def _compute_detection_raw_metrics(request: EvaluationRequest, iq: np.ndarray) -> list[RawMetric]:
    """计算探测性能指标。"""
    settings = request.evaluation
    metrics = compute_detection_metrics(
        iq,
        noise_variance=settings.noise_variance,
        pfa=settings.pfa,
        target_pd=settings.target_pd,
    )
    return [
        _available_metric("detection.pfa", "detection", metrics.pfa, "", "虚警概率"),
        _available_metric(
            "detection.threshold_normalized",
            "detection",
            metrics.threshold_normalized,
            "",
            "归一化检测门限",
        ),
        _available_metric("detection.pd", "detection", metrics.pd, "", "检测概率"),
        _available_metric(
            "detection.output_snr_db",
            "detection",
            metrics.output_snr_db,
            "dB",
            "匹配滤波输出 SNR",
        ),
        _metric_or_unavailable(
            "detection.required_output_snr_db",
            "detection",
            metrics.required_output_snr_db,
            "dB",
            "未提供 target_pd，无法计算所需输出 SNR。",
            "目标 Pd 所需输出 SNR",
        ),
    ]


def _compute_jamming_raw_metrics(request: EvaluationRequest, iq: np.ndarray) -> list[RawMetric]:
    """计算宽带噪声压制干扰指标。"""
    if not request.jammer.enabled or request.jammer.jammer_type != "noise":
        reason = "未启用 wideband complex Gaussian noise jamming 模型。"
        return [
            _unavailable_metric("anti_jamming.clean_pd", "anti_jamming", reason),
            _unavailable_metric("anti_jamming.jammed_pd", "anti_jamming", reason),
            _unavailable_metric("anti_jamming.pd_retention", "anti_jamming", reason),
            _unavailable_metric("anti_jamming.jammed_output_sinr_db", "anti_jamming", reason),
            _unavailable_metric("anti_jamming.jamming_margin_jsr_db", "anti_jamming", reason),
        ]

    settings = request.evaluation
    metrics = compute_wideband_noise_jamming_metrics(
        iq,
        noise_variance=settings.noise_variance,
        pfa=settings.pfa,
        jsr_db=request.jammer.jammer_to_signal_ratio_db,
        target_pd=None,
    )
    raw_metrics = [
        _available_metric(
            "anti_jamming.clean_pd",
            "anti_jamming",
            metrics.clean_pd,
            "",
            "无干扰 Pd",
        ),
        _available_metric(
            "anti_jamming.jammed_pd",
            "anti_jamming",
            metrics.jammed_pd,
            "",
            "干扰下 Pd",
        ),
        _available_metric(
            "anti_jamming.pd_retention",
            "anti_jamming",
            metrics.pd_retention,
            "",
            "检测概率保持率",
        ),
        _available_metric(
            "anti_jamming.jammed_output_sinr_db",
            "anti_jamming",
            metrics.jammed_output_sinr_db,
            "dB",
            "干扰下输出 SINR",
        ),
    ]
    if settings.target_pd is None:
        raw_metrics.append(
            _unavailable_metric(
                "anti_jamming.jamming_margin_jsr_db",
                "anti_jamming",
                "未提供 target_pd，无法计算抗干扰裕度。",
            ),
        )
        return raw_metrics

    try:
        margin_linear = compute_wideband_noise_jamming_margin_jsr_linear(
            iq,
            settings.noise_variance,
            settings.pfa,
            settings.target_pd,
        )
        margin_db = compute_wideband_noise_jamming_margin_jsr_db(
            iq,
            settings.noise_variance,
            settings.pfa,
            settings.target_pd,
        )
    except JammingModelError as exc:
        raw_metrics.append(
            _unavailable_metric(
                "anti_jamming.jamming_margin_jsr_db",
                "anti_jamming",
                str(exc),
            ),
        )
    else:
        raw_metrics.append(
            _available_metric(
                "anti_jamming.jamming_margin_jsr_db",
                "anti_jamming",
                margin_db,
                "dB",
                f"抗干扰裕度 JSR，线性值 {margin_linear:g}",
            ),
        )
    return raw_metrics


def _compute_lpi_raw_metrics(request: EvaluationRequest, iq: np.ndarray) -> list[RawMetric]:
    """计算低截获暴露特征。"""
    settings = request.evaluation
    metrics = compute_lpi_exposure_metrics(
        iq,
        sample_rate_hz=request.waveform.sample_rate_hz,
        bandwidth_hz=request.waveform.bandwidth_hz,
        pulse_width_s=request.waveform.pulse_width_s,
        occupied_power_fraction=settings.occupied_power_fraction,
        prf_hz=settings.prf_hz,
        pri_s=settings.pri_s,
    )
    raw_metrics = [
        _available_metric("lpi.peak_power_w", "lpi", metrics.peak_power_w, "W", "峰值功率"),
        _available_metric("lpi.average_power_w", "lpi", metrics.average_power_w, "W", "平均功率"),
        _available_metric("lpi.papr_db", "lpi", metrics.papr_db, "dB", "PAPR"),
        _available_metric(
            "lpi.nominal_avg_psd_w_per_hz",
            "lpi",
            metrics.nominal_avg_psd_w_per_hz,
            "W/Hz",
            "名义平均 PSD",
        ),
        _available_metric(
            "lpi.occupied_bandwidth_hz",
            "lpi",
            metrics.occupied_bandwidth_hz,
            "Hz",
            "中心占用带宽",
        ),
        _available_metric("lpi.tbp", "lpi", metrics.tbp, "", "时宽带宽积"),
    ]
    raw_metrics.append(
        _metric_or_unavailable(
            "lpi.duty_cycle",
            "lpi",
            metrics.duty_cycle,
            "",
            "未提供 prf_hz 或 pri_s，不计算占空比。",
            "占空比",
        ),
    )
    return raw_metrics


def _compute_waveform_preview_chart(
    request: EvaluationRequest,
    waveform_signal: Any,
) -> dict[str, Any]:
    """生成仅用于 UI 预览的实部波形，并在脉冲尾部补零显示。"""
    sample_rate_hz = request.waveform.sample_rate_hz
    pulse_width_s = request.waveform.pulse_width_s
    preview_duration_s = 2.0 * pulse_width_s
    total_preview_samples = int(round(preview_duration_s * sample_rate_hz)) + 1
    if total_preview_samples < waveform_signal.iq.size:
        raise EvaluationPipelineError("waveform preview 时长不能短于原始波形长度。")

    preview_time_s = np.arange(total_preview_samples, dtype=np.float64) / sample_rate_hz
    preview_real = np.zeros(total_preview_samples, dtype=np.float64)
    preview_real[: waveform_signal.iq.size] = np.real(waveform_signal.iq)
    chart = _series_for_chart(
        preview_time_s,
        preview_real,
        x_key="time_s",
        y_key="real_amplitude",
    )
    chart["pulse_width_s"] = float(pulse_width_s)
    chart["preview_duration_s"] = float(preview_duration_s)
    chart["zero_padded_for_display"] = True
    return chart


def _compute_zero_doppler_chart(iq: np.ndarray) -> dict[str, Any]:
    """生成 zero-Doppler cut 的轻量图表数据。"""
    pc = autocorrelation_matched_filter(iq)
    magnitude = np.abs(pc)
    normalized = magnitude / float(np.max(magnitude))
    delay_samples = np.arange(-(iq.size - 1), iq.size, dtype=int)
    return _series_for_chart(
        delay_samples,
        normalized,
        x_key="delay_samples",
        y_key="magnitude_normalized",
    )


def _compute_ambiguity_heatmap_chart(request: EvaluationRequest, iq: np.ndarray) -> dict[str, Any]:
    """生成轻量二维模糊函数热力图数据。"""
    max_delay = iq.size - 1
    delay_span = min(max_delay, AMBIGUITY_HEATMAP_DELAY_SPAN_SAMPLES)
    delay_count = min(AMBIGUITY_HEATMAP_DELAY_POINTS, 2 * delay_span + 1)
    if delay_count % 2 == 0:
        delay_count -= 1
    delay_samples = np.unique(
        np.round(np.linspace(-delay_span, delay_span, delay_count)).astype(int),
    )
    if not np.any(delay_samples == 0):
        delay_samples = np.sort(
            np.unique(np.concatenate([delay_samples, np.array([0], dtype=int)])),
        )
    doppler_hz = np.linspace(
        -request.evaluation.doppler_max_hz,
        request.evaluation.doppler_max_hz,
        AMBIGUITY_HEATMAP_DOPPLER_POINTS,
    )
    result = compute_ambiguity_function(
        iq,
        sample_rate_hz=request.waveform.sample_rate_hz,
        doppler_hz=doppler_hz,
        delay_samples=delay_samples,
    )
    sample_rate_hz = float(request.waveform.sample_rate_hz)
    delay_samples_list = [int(value) for value in result.delay_samples]
    return {
        "delay_samples": delay_samples_list,
        "delay_us": [float(value / sample_rate_hz * 1e6) for value in result.delay_samples],
        "doppler_hz": [float(value) for value in result.doppler_hz],
        "magnitude_normalized": result.ambiguity_magnitude_normalized.tolist(),
        "matrix_shape": "doppler_by_delay",
        "downsampled": True,
        "sample_rate_hz": sample_rate_hz,
        "delay_window_samples": int(delay_span),
        "doppler_window_hz": float(request.evaluation.doppler_max_hz),
    }


def _compute_spectrum_chart(request: EvaluationRequest, iq: np.ndarray) -> dict[str, Any]:
    """生成轻量双边 PSD 图表数据。"""
    spectrum = compute_two_sided_periodogram_psd(iq, request.waveform.sample_rate_hz)
    chart = _series_for_chart(
        spectrum.frequency_hz,
        spectrum.psd_w_per_hz,
        x_key="frequency_hz",
        y_key="psd_w_per_hz",
    )
    chart["frequency_resolution_hz"] = spectrum.frequency_resolution_hz
    chart["relative_power_error"] = spectrum.relative_power_error
    return chart


def _build_doppler_grid(request: EvaluationRequest) -> np.ndarray:
    """根据评估设置构造包含 0 的对称 Doppler 网格。"""
    settings = request.evaluation
    if settings.doppler_max_hz >= request.waveform.sample_rate_hz / 2.0:
        raise EvaluationPipelineError("doppler_max_hz 必须小于 sample_rate_hz / 2。")
    return np.linspace(-settings.doppler_max_hz, settings.doppler_max_hz, settings.doppler_points)


def _available_metric(
    metric_id: str,
    axis_id: str,
    value: float | int,
    unit: str,
    description: str,
) -> RawMetric:
    """构造可用原始指标；非有限值转为 unavailable。"""
    float_value = float(value)
    if not math.isfinite(float_value):
        return _unavailable_metric(
            metric_id,
            axis_id,
            "指标结果不是有限数值，不能参与 JSON 输出或评分。",
        )
    return RawMetric(
        metric_id=metric_id,
        axis_id=axis_id,
        value=float_value,
        unit=unit,
        available=True,
        description=description,
    )


def _metric_or_unavailable(
    metric_id: str,
    axis_id: str,
    value: float | int | None,
    unit: str,
    unavailable_reason: str,
    description: str,
) -> RawMetric:
    """根据 None 与否构造可用或不可用指标。"""
    if value is None:
        return _unavailable_metric(metric_id, axis_id, unavailable_reason)
    return _available_metric(metric_id, axis_id, value, unit, description)


def _unavailable_metric(metric_id: str, axis_id: str, reason: str) -> RawMetric:
    """构造不可用原始指标。"""
    return RawMetric(
        metric_id=metric_id,
        axis_id=axis_id,
        value=None,
        unit="",
        available=False,
        reason=reason,
    )


def _series_for_chart(
    x: np.ndarray,
    y: np.ndarray,
    *,
    x_key: str,
    y_key: str,
    max_points: int = 512,
) -> dict[str, Any]:
    """将曲线数据下采样为适合 JSON 输出的图表数据。"""
    x_array = np.asarray(x)
    y_array = np.asarray(y)
    if x_array.shape != y_array.shape:
        raise EvaluationPipelineError("chart series 的 x 和 y 形状必须一致。")
    if x_array.size > max_points:
        indices = np.linspace(0, x_array.size - 1, max_points, dtype=int)
        x_array = x_array[indices]
        y_array = y_array[indices]
        downsampled = True
    else:
        downsampled = False
    return {
        x_key: [float(value) for value in x_array],
        y_key: [float(value) for value in y_array],
        "downsampled": downsampled,
        "source_points": int(np.asarray(x).size),
    }
