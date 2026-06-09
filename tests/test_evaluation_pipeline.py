"""完整算法评估流水线测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from radar_eval_core.evaluation_pipeline import compute_waveform_evaluation
from radar_eval_core.schemas import EvaluationRequest
from radar_eval_core.scoring import ScoringConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_lfm_default_config_runs_complete_evaluation() -> None:
    """测试默认 LFM 配置可以跑完整评估并输出 6 个维度。"""
    request = _load_request(PROJECT_ROOT / "configs" / "lfm_default.json")
    scoring_config = _load_scoring_config(PROJECT_ROOT / "configs" / "scoring_default.json")

    result = compute_waveform_evaluation(request, scoring_config)

    assert len(result.axis_scores) == 6
    assert {axis.axis_id for axis in result.axis_scores} == {
        "detection",
        "resolution",
        "sidelobe_ambiguity",
        "anti_jamming",
        "lpi",
        "engineering",
    }
    assert 0.0 <= result.overall_score <= 100.0
    assert all(axis.score is None or 0.0 <= axis.score <= 100.0 for axis in result.axis_scores)
    metric_ids = {metric.metric_id for metric in result.raw_metrics}
    assert "detection.pd" in metric_ids
    assert "resolution.range_resolution_m" in metric_ids
    assert "anti_jamming.pd_retention" in metric_ids
    assert "lpi.nominal_avg_psd_w_per_hz" in metric_ids


def test_missing_cpi_marks_velocity_related_metrics_unavailable() -> None:
    """测试缺少 CPI 参数时不猜测多普勒和速度分辨率。"""
    data = _read_json(PROJECT_ROOT / "configs" / "lfm_default.json")
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
    assert heatmap["sample_rate_hz"] == pytest.approx(request.waveform.sample_rate_hz)
    assert len(heatmap["delay_us"]) == len(heatmap["delay_samples"])
    for delay_sample, delay_us in zip(heatmap["delay_samples"], heatmap["delay_us"], strict=True):
        assert delay_us == pytest.approx(delay_sample / request.waveform.sample_rate_hz * 1e6)
    assert max(abs(value) for value in heatmap["delay_samples"]) <= 256
    assert heatmap["matrix_shape"] == "doppler_by_delay"
    assert "ambiguity_complex" not in result.chart_data
    assert "ambiguity_magnitude" not in result.chart_data


def test_waveform_preview_uses_real_amplitude_not_magnitude() -> None:
    """测试波形预览使用实部，并且仅在 chart data 中做尾部补零。"""
    request = _load_request(PROJECT_ROOT / "configs" / "lfm_default.json")
    scoring_config = _load_scoring_config(PROJECT_ROOT / "configs" / "scoring_default.json")

    result = compute_waveform_evaluation(request, scoring_config)
    preview = result.chart_data["waveform_preview"]

    assert "real_amplitude" in preview
    assert "magnitude" not in preview
    assert preview["downsampled"] is False
    assert len(preview["time_s"]) == preview["source_points"]
    assert len(preview["real_amplitude"]) == preview["source_points"]
    assert preview["zero_padded_for_display"] is True
    assert preview["preview_duration_s"] == pytest.approx(2.0 * request.waveform.pulse_width_s)
    tail_values = [
        value
        for time_s, value in zip(preview["time_s"], preview["real_amplitude"], strict=True)
        if time_s >= request.waveform.pulse_width_s
    ]
    assert all(abs(value) < 1e-12 for value in tail_values)


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
    return EvaluationRequest.model_validate(_read_json(path))


def _load_scoring_config(path: Path) -> ScoringConfig:
    """从 JSON 加载 ScoringConfig。"""
    return ScoringConfig.model_validate(_read_json(path))


def _read_json(path: Path) -> dict:
    """读取 JSON 配置。"""
    return json.loads(path.read_text(encoding="utf-8"))
