"""完整算法评估流水线测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from radar_eval_core.evaluation_pipeline import compute_waveform_evaluation
from radar_eval_core.schemas import EvaluationRequest, derive_total_pulse_width_s
from radar_eval_core.scoring import ScoringConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_lfm_default_config_runs_complete_evaluation() -> None:
    """测试默认 LFM 配置可以跑完整评估并输出默认评分维度。"""
    request = _load_request(PROJECT_ROOT / "configs" / "lfm_default.json")
    scoring_config = _load_scoring_config(PROJECT_ROOT / "configs" / "scoring_default.json")

    assert request.waveform.bandwidth_hz == pytest.approx(10e6)
    assert request.waveform.pulse_width_s == pytest.approx(10e-6)
    assert request.waveform.sample_rate_hz == pytest.approx(50e6)
    assert request.waveform.peak_power_w == pytest.approx(1000.0)

    result = compute_waveform_evaluation(request, scoring_config)
    axes = {axis.axis_id: axis for axis in result.axis_scores}

    assert len(result.axis_scores) == 5
    assert set(axes) == {
        "detection",
        "resolution",
        "sidelobe_ambiguity",
        "anti_jamming",
        "lpi",
    }
    assert 0.0 <= result.overall_score <= 100.0
    assert all(axis.score is None or 0.0 <= axis.score <= 100.0 for axis in result.axis_scores)
    metric_ids = {metric.metric_id for metric in result.raw_metrics}
    assert "detection.pd" in metric_ids
    assert "resolution.range_resolution_m" in metric_ids
    assert "anti_jamming.pd_retention" in metric_ids
    assert "lpi.nominal_avg_psd_w_per_hz" in metric_ids
    assert "sidelobe_ambiguity.zero_doppler_islr_db" in metric_ids
    metrics = {metric.metric_id: metric for metric in result.raw_metrics}
    assert metrics["sidelobe_ambiguity.zero_doppler_pslr_db"].value < -10.0
    assert metrics["sidelobe_ambiguity.zero_doppler_islr_db"].value < 0.0
    sidelobe_axis = axes["sidelobe_ambiguity"]
    assert any(
        metric.name == "sidelobe_ambiguity.zero_doppler_islr_db"
        for metric in sidelobe_axis.metrics
    )


def test_missing_cpi_marks_velocity_related_metrics_unavailable() -> None:
    """测试缺少 CPI 参数时不猜测多普勒和速度分辨率。"""
    data = _read_request_json(PROJECT_ROOT / "configs" / "lfm_default.json")
    data["evaluation"]["cpi_s"] = None
    data["evaluation"]["num_pulses"] = None
    data["evaluation"]["prf_hz"] = None
    data["evaluation"]["pri_s"] = None
    request = EvaluationRequest.model_validate(data)
    scoring_config = _load_scoring_config(PROJECT_ROOT / "configs" / "scoring_default.json")

    result = compute_waveform_evaluation(request, scoring_config)
    metrics = {metric.metric_id: metric for metric in result.raw_metrics}

    assert metrics["resolution.doppler_resolution_hz"].available is False
    assert metrics["resolution.velocity_resolution_mps"].available is False
    assert metrics["resolution.doppler_resolution_hz"].value is None
    assert metrics["resolution.velocity_resolution_mps"].value is None


def test_rect_waveform_evaluation_marks_unfit_sidelobe_metrics_unavailable() -> None:
    """测试矩形脉冲在默认主瓣定义不适用时不中断完整评估。"""
    data = _read_request_json(PROJECT_ROOT / "configs" / "lfm_default.json")
    data["waveform"].update(
        {
            "name": "rect_smoke",
            "waveform_type": "rect",
            "bandwidth_hz": 20e6,
            "pulse_width_s": 10e-6,
            "sample_rate_hz": 50e6,
        },
    )
    request = EvaluationRequest.model_validate(data)
    scoring_config = _load_scoring_config(PROJECT_ROOT / "configs" / "scoring_default.json")

    result = compute_waveform_evaluation(request, scoring_config)
    metrics = {metric.metric_id: metric for metric in result.raw_metrics}

    assert 0.0 <= result.overall_score <= 100.0
    assert metrics["sidelobe_ambiguity.zero_doppler_pslr_db"].available is False
    assert metrics["sidelobe_ambiguity.zero_doppler_islr_db"].available is False
    assert metrics["sidelobe_ambiguity.mainlobe_width_samples"].available is False
    assert "主瓣边界不适用" in (
        metrics["sidelobe_ambiguity.zero_doppler_pslr_db"].reason or ""
    )
    assert metrics["sidelobe_ambiguity.doppler_tolerance_hz"].available is True
    assert metrics["detection.pd"].available is True


def test_zero_doppler_islr_reasonable_across_waveform_types() -> None:
    """测试不同波形的零多普勒 ISLR 结果符合当前主瓣定义。"""
    scoring_config = _load_scoring_config(PROJECT_ROOT / "configs" / "scoring_default.json")
    lfm = compute_waveform_evaluation(
        _load_request(PROJECT_ROOT / "configs" / "lfm_default.json"),
        scoring_config,
    )
    phase_code = compute_waveform_evaluation(
        _load_request(PROJECT_ROOT / "configs" / "phase_code_default.json"),
        scoring_config,
    )
    rect_data = _read_request_json(PROJECT_ROOT / "configs" / "lfm_default.json")
    rect_data["waveform"].update(
        {
            "name": "rect_islr_smoke",
            "waveform_type": "rect",
            "bandwidth_hz": 20e6,
            "pulse_width_s": 10e-6,
            "sample_rate_hz": 50e6,
        },
    )
    rect = compute_waveform_evaluation(
        EvaluationRequest.model_validate(rect_data),
        scoring_config,
    )

    lfm_metrics = {metric.metric_id: metric for metric in lfm.raw_metrics}
    phase_metrics = {metric.metric_id: metric for metric in phase_code.raw_metrics}
    rect_metrics = {metric.metric_id: metric for metric in rect.raw_metrics}
    lfm_pslr = lfm_metrics["sidelobe_ambiguity.zero_doppler_pslr_db"].value
    lfm_islr = lfm_metrics["sidelobe_ambiguity.zero_doppler_islr_db"].value
    phase_pslr = phase_metrics["sidelobe_ambiguity.zero_doppler_pslr_db"].value
    phase_islr = phase_metrics["sidelobe_ambiguity.zero_doppler_islr_db"].value
    rect_islr = rect_metrics["sidelobe_ambiguity.zero_doppler_islr_db"]

    assert lfm_pslr is not None
    assert lfm_islr is not None
    assert phase_pslr is not None
    assert phase_islr is not None
    assert lfm_pslr < lfm_islr < 0.0
    assert phase_pslr < phase_islr < 0.0
    assert phase_islr < lfm_islr
    assert rect_islr.available is False
    assert rect_islr.value is None
    assert "主瓣边界不适用" in (rect_islr.reason or "")


def test_chart_data_does_not_include_full_ambiguity_matrix() -> None:
    """测试图表数据不包含完整二维模糊函数矩阵。"""
    request = _load_request(PROJECT_ROOT / "configs" / "lfm_default.json")
    scoring_config = _load_scoring_config(PROJECT_ROOT / "configs" / "scoring_default.json")

    result = compute_waveform_evaluation(request, scoring_config)

    assert "zero_delay_doppler_cut" in result.chart_data
    assert "zero_doppler_cut" in result.chart_data
    heatmap = result.chart_data["ambiguity_heatmap"]
    assert 0 in heatmap["delay_samples"]
    assert 0.0 in heatmap["doppler_hz"]
    assert len(heatmap["magnitude_normalized"]) == len(heatmap["doppler_hz"])
    assert len(heatmap["magnitude_normalized"][0]) == len(heatmap["delay_samples"])
    assert len(heatmap["delay_samples"]) == 257
    assert len(heatmap["doppler_hz"]) == 257
    assert heatmap["sample_rate_hz"] == pytest.approx(request.waveform.sample_rate_hz)
    assert len(heatmap["delay_us"]) == len(heatmap["delay_samples"])
    for delay_sample, delay_us in zip(heatmap["delay_samples"], heatmap["delay_us"], strict=True):
        assert delay_us == pytest.approx(delay_sample / request.waveform.sample_rate_hz * 1e6)
    total_samples = int(round(request.waveform.sample_rate_hz * request.waveform.pulse_width_s))
    assert max(abs(value) for value in heatmap["delay_samples"]) == total_samples - 1
    assert heatmap["delay_window_source"] == "full_pulse_width"
    assert heatmap["doppler_window_hz"] == pytest.approx(request.waveform.bandwidth_hz)
    assert heatmap["doppler_window_source"] == "lfm_bandwidth"
    assert heatmap["display_model"] == "discrete_fft_ambiguity_samples"
    assert heatmap["matrix_shape"] == "doppler_by_delay"
    assert "ambiguity_complex" not in result.chart_data
    assert "ambiguity_magnitude" not in result.chart_data


def test_phase_code_ambiguity_heatmap_uses_barker_style_doppler_window() -> None:
    """测试 phase_code 模糊函数图使用类似 Barker 示例的 Doppler 显示窗口。"""
    request = _load_request(PROJECT_ROOT / "configs" / "phase_code_default.json")
    scoring_config = _load_scoring_config(PROJECT_ROOT / "configs" / "scoring_default.json")

    assert request.waveform.phase_code == [1, 1, 1, 1, 1, -1, -1, 1, 1, -1, 1, -1, 1]
    assert request.waveform.pulse_width_s == pytest.approx(1e-6)
    assert request.waveform.bandwidth_hz == pytest.approx(1e6)
    assert request.waveform.peak_power_w == pytest.approx(1000.0)

    result = compute_waveform_evaluation(request, scoring_config)
    heatmap = result.chart_data["ambiguity_heatmap"]
    metrics = {metric.metric_id: metric for metric in result.raw_metrics}
    total_pulse_width_s = derive_total_pulse_width_s(
        request.waveform.waveform_type,
        request.waveform.pulse_width_s,
        phase_code=request.waveform.phase_code,
    )

    assert metrics["sidelobe_ambiguity.zero_doppler_pslr_db"].value < -20.0
    assert metrics["sidelobe_ambiguity.zero_doppler_islr_db"].value < -10.0
    assert metrics["engineering.tbp"].value == pytest.approx(13.0)
    assert heatmap["doppler_window_hz"] == pytest.approx(6.0 / total_pulse_width_s)
    assert heatmap["doppler_window_source"] == "phase_code_6_over_total_pulse_width"
    assert heatmap["display_model"] == "discrete_fft_ambiguity_samples"
    assert len(heatmap["delay_samples"]) == 257
    assert len(heatmap["doppler_hz"]) == 257


def test_waveform_preview_uses_normalized_real_amplitude_not_magnitude() -> None:
    """测试波形预览使用归一化实部，并且仅在 chart data 中做尾部补零。"""
    request = _load_request(PROJECT_ROOT / "configs" / "lfm_default.json")
    scoring_config = _load_scoring_config(PROJECT_ROOT / "configs" / "scoring_default.json")

    result = compute_waveform_evaluation(request, scoring_config)
    preview = result.chart_data["waveform_preview"]

    assert "real_amplitude" in preview
    assert "magnitude" not in preview
    assert preview["downsampled"] is False
    assert preview["amplitude_unit"] == "normalized"
    assert preview["normalization_reference"] == "max_abs_iq"
    assert preview["normalization_factor"] == pytest.approx(request.waveform.peak_power_w**0.5)
    assert len(preview["time_s"]) == preview["source_points"]
    assert len(preview["real_amplitude"]) == preview["source_points"]
    assert max(abs(value) for value in preview["real_amplitude"]) <= 1.0 + 1e-12
    assert preview["zero_padded_for_display"] is True
    assert preview["preview_duration_s"] == pytest.approx(2.0 * request.waveform.pulse_width_s)
    tail_values = [
        value
        for time_s, value in zip(preview["time_s"], preview["real_amplitude"], strict=True)
        if time_s >= request.waveform.pulse_width_s
    ]
    assert all(abs(value) < 1e-12 for value in tail_values)

    low_power_data = _read_request_json(PROJECT_ROOT / "configs" / "lfm_default.json")
    low_power_data["waveform"]["peak_power_w"] = 1.0
    low_power_result = compute_waveform_evaluation(
        EvaluationRequest.model_validate(low_power_data),
        scoring_config,
    )
    low_power_preview = low_power_result.chart_data["waveform_preview"]

    assert low_power_preview["real_amplitude"] == pytest.approx(preview["real_amplitude"])


def test_spectrum_chart_uses_full_grid_and_relative_db() -> None:
    """测试频谱图表数据保留完整频率网格，并提供相对 dB 显示字段。"""
    request = _load_request(PROJECT_ROOT / "configs" / "lfm_default.json")
    scoring_config = _load_scoring_config(PROJECT_ROOT / "configs" / "scoring_default.json")

    result = compute_waveform_evaluation(request, scoring_config)
    spectrum = result.chart_data["spectrum_psd"]

    assert spectrum["downsampled"] is False
    assert len(spectrum["frequency_hz"]) == spectrum["source_points"]
    assert len(spectrum["frequency_mhz"]) == spectrum["source_points"]
    assert len(spectrum["psd_w_per_hz"]) == spectrum["source_points"]
    assert max(spectrum["psd_w_per_hz"]) > 0.0
    assert len(spectrum["psd_relative_db"]) == spectrum["source_points"]
    assert max(spectrum["psd_relative_db"]) == pytest.approx(0.0)
    assert min(spectrum["psd_relative_db"]) >= -120.0


def _load_request(path: Path) -> EvaluationRequest:
    """从 JSON 加载 EvaluationRequest。"""
    return EvaluationRequest.model_validate(_read_request_json(path))


def _load_scoring_config(path: Path) -> ScoringConfig:
    """从 JSON 加载 ScoringConfig。"""
    return ScoringConfig.model_validate(_read_json(path))


def _read_json(path: Path) -> dict:
    """读取 JSON 配置。"""
    return json.loads(path.read_text(encoding="utf-8"))


def _read_request_json(path: Path) -> dict:
    """读取波形配置并合并默认场景与环境配置。"""
    data = _read_json(path)
    data.update(_read_json(PROJECT_ROOT / "configs" / "scenario_default.json"))
    return data
