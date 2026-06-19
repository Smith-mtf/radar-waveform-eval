"""本地模板报告服务 smoke 测试。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from desktop_app.services.evaluation_service import EvaluationService
from desktop_app.services.report_service import (
    ReportDocument,
    build_report_input,
    generate_llm_report_placeholder,
    generate_local_template_report,
    render_report_html,
    render_report_markdown,
)
from radar_eval_core.evaluation_pipeline import compute_waveform_evaluation
from radar_eval_core.scoring import ScoringConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_generate_local_template_report_smoke() -> None:
    """测试本地模板报告能从 EvaluationResult 生成结构化文档。"""
    result, scoring_config = _sample_result()

    report_input = build_report_input(result, scoring_config=scoring_config)
    report = generate_local_template_report(result, scoring_config=scoring_config)

    assert report_input["waveform_name"] == result.request.waveform.name
    assert report_input["raw_metrics"]
    assert isinstance(report, ReportDocument)
    assert report.waveform_name == result.request.waveform.name
    assert any(section.title == "总体结论" for section in report.sections)
    assert any(section.title == "模型假设与限制" for section in report.sections)
    assert all(section.title != "工程可实现性分析" for section in report.sections)


def test_report_renderers_and_llm_placeholder_smoke() -> None:
    """测试 Markdown、HTML 渲染和 LLM 占位入口。"""
    result, scoring_config = _sample_result()
    report = generate_local_template_report(result, scoring_config=scoring_config)

    markdown = render_report_markdown(report)
    html = render_report_html(report)
    placeholder = generate_llm_report_placeholder(build_report_input(result))

    assert f"# {report.title}" in markdown
    assert "总体结论" in markdown
    assert "模型假设与限制" in markdown
    assert "<!doctype html>" in html
    assert "<html lang=\"zh-CN\">" in html
    assert "外部模型接口未配置" in placeholder.summary


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
