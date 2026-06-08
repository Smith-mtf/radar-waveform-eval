"""导出服务测试。"""

from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path

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
from radar_eval_core.schemas import EvaluationRequest
from radar_eval_core.scoring import ScoringConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_export_evaluation_json(tmp_path: Path) -> None:
    """测试导出完整评估 JSON。"""
    result, _scoring_config = _sample_result()
    path = tmp_path / "evaluation_result.json"

    export_evaluation_json(result, path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["overall_score"] == result.overall_score


def test_export_raw_metrics_csv(tmp_path: Path) -> None:
    """测试导出原始指标 CSV。"""
    result, _scoring_config = _sample_result()
    path = tmp_path / "raw_metrics.csv"

    export_raw_metrics_csv(result, path)

    rows = list(csv.DictReader(path.open("r", encoding="utf-8", newline="")))
    assert rows
    assert "metric_id" in rows[0]
    assert "unavailable_reason" in rows[0]


def test_export_axis_scores_csv(tmp_path: Path) -> None:
    """测试导出评分 CSV。"""
    result, _scoring_config = _sample_result()
    path = tmp_path / "axis_scores.csv"

    export_axis_scores_csv(result, path)

    rows = list(csv.DictReader(path.open("r", encoding="utf-8", newline="")))
    assert rows
    assert "axis_id" in rows[0]
    assert "score" in rows[0]


def test_export_chart_data_json(tmp_path: Path) -> None:
    """测试导出 chart_data JSON。"""
    result, _scoring_config = _sample_result()
    path = tmp_path / "chart_data.json"

    export_chart_data_json(result, path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "ambiguity_heatmap" in payload


def test_export_markdown_and_html(tmp_path: Path) -> None:
    """测试导出 Markdown 和 HTML 报告。"""
    result, scoring_config = _sample_result()
    report = generate_local_template_report(result, scoring_config=scoring_config)
    markdown = render_report_markdown(report)
    html = render_report_html(report)
    markdown_path = tmp_path / "nested" / "report.md"
    html_path = tmp_path / "nested" / "report.html"

    export_report_markdown(markdown, markdown_path)
    export_report_html(html, html_path)

    assert markdown_path.exists()
    assert html_path.exists()
    assert markdown_path.stat().st_size > 0
    assert html_path.stat().st_size > 0


@lru_cache(maxsize=1)
def _sample_result():
    request = EvaluationRequest.model_validate(
        _read_json(PROJECT_ROOT / "configs" / "lfm_default.json"),
    )
    scoring_config = ScoringConfig.model_validate(
        _read_json(PROJECT_ROOT / "configs" / "scoring_default.json"),
    )
    return compute_waveform_evaluation(request, scoring_config), scoring_config


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
