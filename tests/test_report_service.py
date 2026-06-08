"""本地模板报告服务测试。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from desktop_app.services.report_service import (
    ReportDocument,
    build_report_input,
    generate_llm_report_placeholder,
    generate_local_template_report,
    render_report_html,
    render_report_markdown,
)
from radar_eval_core.evaluation_pipeline import compute_waveform_evaluation
from radar_eval_core.schemas import EvaluationRequest
from radar_eval_core.scoring import ScoringConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_build_report_input_handles_evaluation_result() -> None:
    """测试报告输入可从 EvaluationResult 中抽取。"""
    result, scoring_config = _sample_result()

    report_input = build_report_input(result, scoring_config=scoring_config)

    assert report_input["waveform_name"] == result.request.waveform.name
    assert report_input["overall_score"] == result.overall_score
    assert report_input["raw_metrics"]
    assert report_input["axis_scores"]
    assert report_input["scoring_config"]["config_name"] == scoring_config.config_name


def test_generate_local_template_report_returns_document() -> None:
    """测试本地模板报告可生成 ReportDocument。"""
    result, scoring_config = _sample_result()

    report = generate_local_template_report(result, scoring_config=scoring_config)

    assert isinstance(report, ReportDocument)
    assert report.waveform_name == result.request.waveform.name
    assert any(section.title == "总体结论" for section in report.sections)
    assert any(section.title == "模型假设与限制" for section in report.sections)


def test_render_report_markdown_contains_required_sections() -> None:
    """测试 Markdown 报告包含标题、总体结论和限制说明。"""
    result, scoring_config = _sample_result()
    report = generate_local_template_report(result, scoring_config=scoring_config)

    markdown = render_report_markdown(report)

    assert f"# {report.title}" in markdown
    assert "总体结论" in markdown
    assert "模型假设与限制" in markdown
    assert "未包含完整侦收机模型" in markdown


def test_render_report_html_contains_basic_structure() -> None:
    """测试 HTML 报告包含基础 HTML 结构。"""
    result, scoring_config = _sample_result()
    report = generate_local_template_report(result, scoring_config=scoring_config)

    html = render_report_html(report)

    assert "<!doctype html>" in html
    assert "<html lang=\"zh-CN\">" in html
    assert "<section>" in html


def test_llm_placeholder_does_not_call_external_service() -> None:
    """测试 LLM 占位函数给出明确未配置提示。"""
    result, _scoring_config = _sample_result()
    report_input = build_report_input(result)

    report = generate_llm_report_placeholder(report_input)

    assert "外部模型接口未配置" in report.summary
    assert "未上传数据" in report.sections[0].content


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
