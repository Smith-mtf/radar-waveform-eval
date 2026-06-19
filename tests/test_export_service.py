"""导出服务 smoke 测试。"""

from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path

from desktop_app.services.evaluation_service import EvaluationService
from desktop_app.services.export_service import (
    export_axis_scores_csv,
    export_chart_data_json,
    export_evaluation_json,
    export_raw_metrics_csv,
    export_report_html,
    export_report_markdown,
)
from desktop_app.services.report_service import (
    generate_local_template_report,
    render_report_html,
    render_report_markdown,
)
from radar_eval_core.evaluation_pipeline import compute_waveform_evaluation
from radar_eval_core.scoring import ScoringConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_export_service_writes_expected_outputs(tmp_path: Path) -> None:
    """测试导出服务能写出主要交付文件。"""
    result, scoring_config = _sample_result()
    report = generate_local_template_report(result, scoring_config=scoring_config)

    evaluation_path = tmp_path / "evaluation_result.json"
    raw_metrics_path = tmp_path / "raw_metrics.csv"
    axis_scores_path = tmp_path / "axis_scores.csv"
    chart_data_path = tmp_path / "chart_data.json"
    markdown_path = tmp_path / "report" / "report.md"
    html_path = tmp_path / "report" / "report.html"

    export_evaluation_json(result, evaluation_path)
    export_raw_metrics_csv(result, raw_metrics_path)
    export_axis_scores_csv(result, axis_scores_path)
    export_chart_data_json(result, chart_data_path)
    export_report_markdown(render_report_markdown(report), markdown_path)
    export_report_html(render_report_html(report), html_path)

    for path in [
        evaluation_path,
        raw_metrics_path,
        axis_scores_path,
        chart_data_path,
        markdown_path,
        html_path,
    ]:
        assert path.exists()
        assert path.stat().st_size > 0

    assert json.loads(evaluation_path.read_text(encoding="utf-8"))["overall_score"]
    assert "ambiguity_heatmap" in json.loads(chart_data_path.read_text(encoding="utf-8"))
    assert list(csv.DictReader(raw_metrics_path.open("r", encoding="utf-8", newline="")))
    assert list(csv.DictReader(axis_scores_path.open("r", encoding="utf-8", newline="")))


@lru_cache(maxsize=1)
def _sample_result():
    request = EvaluationService().load_request_with_scenario_environment(
        PROJECT_ROOT / "configs" / "lfm_default.json",
        PROJECT_ROOT / "configs" / "scenario_default.json",
    )
    scoring_config = ScoringConfig.model_validate(
        _read_json(PROJECT_ROOT / "configs" / "scoring_default.json"),
    )
    return compute_waveform_evaluation(request, scoring_config), scoring_config


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
