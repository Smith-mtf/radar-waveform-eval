"""本地模板报告服务。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from typing import Any

from radar_eval_core.schemas import AxisScore, EvaluationResult, RawMetric
from radar_eval_core.scoring import ScoringConfig


@dataclass(slots=True)
class ReportSection:
    """报告章节。"""

    title: str
    content: str
    level: int = 1


@dataclass(slots=True)
class ReportDocument:
    """本地模板报告文档。"""

    title: str
    waveform_name: str
    generated_at: str
    summary: str
    sections: list[ReportSection] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    source_result_id: str | None = None


def build_report_input(
    result: EvaluationResult,
    *,
    scoring_config: ScoringConfig | None = None,
    comparison_results: list[EvaluationResult] | None = None,
    source_result_id: str | None = None,
) -> dict[str, Any]:
    """从 EvaluationResult 抽取报告输入，不计算新指标，也不修改原始结果。"""
    unavailable_metrics = [metric for metric in result.raw_metrics if not metric.available]
    return {
        "source_result_id": source_result_id,
        "waveform_name": result.request.waveform.name,
        "waveform_type": result.request.waveform.waveform_type,
        "overall_score": result.overall_score,
        "axis_scores": [axis.model_dump(mode="json") for axis in result.axis_scores],
        "raw_metrics": [metric.model_dump(mode="json") for metric in result.raw_metrics],
        "unavailable_metrics": [
            metric.model_dump(mode="json") for metric in unavailable_metrics
        ],
        "request": result.request.model_dump(mode="json"),
        "summary": result.summary,
        "scoring_config": None
        if scoring_config is None
        else scoring_config.model_dump(mode="json"),
        "comparison_results": [
            {
                "waveform_name": item.request.waveform.name,
                "overall_score": item.overall_score,
                "axis_scores": [axis.model_dump(mode="json") for axis in item.axis_scores],
            }
            for item in comparison_results or []
        ],
    }


def generate_local_template_report(
    result: EvaluationResult,
    *,
    scoring_config: ScoringConfig | None = None,
    comparison_results: list[EvaluationResult] | None = None,
    source_result_id: str | None = None,
) -> ReportDocument:
    """基于已有 EvaluationResult 生成本地模板报告，不调用外部模型。"""
    report_input = build_report_input(
        result,
        scoring_config=scoring_config,
        comparison_results=comparison_results,
        source_result_id=source_result_id,
    )
    metrics = {metric.metric_id: metric for metric in result.raw_metrics}
    axis_by_id = {axis.axis_id: axis for axis in result.axis_scores}
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    assumptions = _default_assumptions(scoring_config)
    limitations = _default_limitations()
    recommendations = _build_recommendations(result, metrics)
    sections = [
        ReportSection("总体结论", _overall_section(result, report_input)),
        ReportSection("探测性能分析", _metric_section(metrics, _DETECTION_METRICS)),
        ReportSection("分辨能力分析", _resolution_section(metrics)),
        ReportSection("旁瓣与模糊控制分析", _sidelobe_section(metrics)),
        ReportSection("抗干扰性能分析", _jamming_section(metrics)),
        ReportSection("反侦察 / 低截获特征分析", _lpi_section(metrics)),
        ReportSection("工程可实现性分析", _engineering_section(metrics)),
        ReportSection("横向对比说明", _comparison_section(result, comparison_results or [])),
        ReportSection(
            "模型假设与限制",
            _list_text([*assumptions, *limitations]),
        ),
        ReportSection("优化建议", _list_text(recommendations)),
    ]
    return ReportDocument(
        title=f"{result.request.waveform.name} 评估报告",
        waveform_name=result.request.waveform.name,
        generated_at=generated_at,
        summary=_summary_sentence(result, axis_by_id),
        sections=sections,
        assumptions=assumptions,
        limitations=limitations,
        recommendations=recommendations,
        source_result_id=source_result_id,
    )


def render_report_markdown(report: ReportDocument) -> str:
    """将 ReportDocument 渲染为 Markdown 文本。"""
    lines = [
        f"# {report.title}",
        "",
        f"- 波形名称: {report.waveform_name}",
        f"- 生成时间: {report.generated_at}",
    ]
    if report.source_result_id:
        lines.append(f"- 来源结果 ID: {report.source_result_id}")
    lines.extend(["", "## 摘要", "", report.summary, ""])
    for section in report.sections:
        heading = "#" * max(2, min(section.level + 1, 6))
        lines.extend([f"{heading} {section.title}", "", section.content, ""])
    return "\n".join(lines).rstrip() + "\n"


def render_report_html(report: ReportDocument) -> str:
    """将 ReportDocument 渲染为基础 HTML 文本。"""
    sections_html = "\n".join(
        (
            f"<section><h2>{escape(section.title)}</h2>"
            f"<div>{_markdownish_to_html(section.content)}</div></section>"
        )
        for section in report.sections
    )
    source_html = (
        f"<p><strong>来源结果 ID:</strong> {escape(report.source_result_id)}</p>"
        if report.source_result_id
        else ""
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{escape(report.title)}</title>
  <style>
    body {{ font-family: "Microsoft YaHei", "Segoe UI", sans-serif; margin: 32px; color: #1f2933; }}
    h1, h2 {{ color: #102a43; }}
    section {{ border-top: 1px solid #d7dee6; padding-top: 16px; margin-top: 20px; }}
    .meta {{ color: #52606d; }}
    li {{ margin: 4px 0; }}
  </style>
</head>
<body>
  <h1>{escape(report.title)}</h1>
  <div class="meta">
    <p><strong>波形名称:</strong> {escape(report.waveform_name)}</p>
    <p><strong>生成时间:</strong> {escape(report.generated_at)}</p>
    {source_html}
  </div>
  <h2>摘要</h2>
  <p>{escape(report.summary)}</p>
  {sections_html}
</body>
</html>
"""


def generate_llm_report_placeholder(report_input: dict[str, Any]) -> ReportDocument:
    """返回外部模型报告未配置提示，不读取密钥、不调用网络。"""
    waveform_name = str(report_input.get("waveform_name") or "unknown_waveform")
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    return ReportDocument(
        title=f"{waveform_name} 外部模型报告占位",
        waveform_name=waveform_name,
        generated_at=generated_at,
        summary="外部模型接口未配置；本阶段仅提供本地模板报告。",
        sections=[
            ReportSection(
                "外部模型接口状态",
                "外部模型接口默认关闭，未读取 API key，未上传数据，也未调用外部服务。",
            ),
        ],
        assumptions=["LLM 只能解释结构化指标结果，不允许计算雷达指标。"],
        limitations=["当前占位函数不会生成外部模型报告。"],
        recommendations=["请使用 generate_local_template_report 生成本地模板报告。"],
        source_result_id=report_input.get("source_result_id"),
    )


_DETECTION_METRICS = [
    "detection.pd",
    "detection.pfa",
    "detection.output_snr_db",
    "detection.required_output_snr_db",
    "detection.threshold_normalized",
]

_RESOLUTION_METRICS = [
    "resolution.range_resolution_m",
    "resolution.range_sample_spacing_m",
    "resolution.velocity_resolution_mps",
    "resolution.doppler_resolution_hz",
    "resolution.cpi_s",
    "resolution.wavelength_m",
]

_SIDELOBE_METRICS = [
    "sidelobe_ambiguity.zero_doppler_pslr_db",
    "sidelobe_ambiguity.zero_doppler_islr_db",
    "sidelobe_ambiguity.mainlobe_width_samples",
    "sidelobe_ambiguity.doppler_tolerance_hz",
]

_JAMMING_METRICS = [
    "anti_jamming.clean_pd",
    "anti_jamming.jammed_pd",
    "anti_jamming.pd_retention",
    "anti_jamming.jammed_output_sinr_db",
    "anti_jamming.jamming_margin_jsr_db",
]

_LPI_METRICS = [
    "lpi.peak_power_w",
    "lpi.average_power_w",
    "lpi.nominal_avg_psd_w_per_hz",
    "lpi.occupied_bandwidth_hz",
    "lpi.tbp",
    "lpi.duty_cycle",
    "lpi.papr_db",
]

_ENGINEERING_METRICS = [
    "engineering.papr_db",
    "engineering.average_power_w",
    "engineering.peak_power_w",
    "engineering.tbp",
]


def _overall_section(result: EvaluationResult, report_input: dict[str, Any]) -> str:
    axis_lines = [
        f"- {axis.name}: {_axis_score_text(axis)}"
        for axis in result.axis_scores
    ]
    scoring_name = "未提供"
    scoring_config = report_input.get("scoring_config")
    if isinstance(scoring_config, dict):
        scoring_name = str(scoring_config.get("config_name") or "未命名评分配置")
    return "\n".join(
        [
            f"综合得分为 {result.overall_score:.2f}。该结论依赖当前评分配置。",
            f"评分配置: {scoring_name}。",
            "",
            *axis_lines,
        ],
    )


def _resolution_section(metrics: dict[str, RawMetric]) -> str:
    return "\n".join(
        [
            _metric_section(metrics, _RESOLUTION_METRICS),
            "",
            "距离分辨率由带宽相关指标表达；距离采样间隔由采样率相关指标表达，二者不是同一个指标。",
        ],
    )


def _sidelobe_section(metrics: dict[str, RawMetric]) -> str:
    return "\n".join(
        [
            _metric_section(metrics, _SIDELOBE_METRICS),
            "",
            "当前版本引用零多普勒旁瓣和 zero-delay Doppler cut 指标，未纳入二维 PSLR / ISLR。",
        ],
    )


def _jamming_section(metrics: dict[str, RawMetric]) -> str:
    return "\n".join(
        [
            _metric_section(metrics, _JAMMING_METRICS),
            "",
            "抗干扰结果对应已实现的宽带复高斯噪声压制干扰模型，不代表全部干扰场景。",
        ],
    )


def _lpi_section(metrics: dict[str, RawMetric]) -> str:
    return "\n".join(
        [
            _metric_section(metrics, _LPI_METRICS),
            "",
            "当前结果为波形暴露特征，不输出截获概率或截获距离比。",
        ],
    )


def _engineering_section(metrics: dict[str, RawMetric]) -> str:
    return "\n".join(
        [
            _metric_section(metrics, _ENGINEERING_METRICS),
            "",
            "处理复杂度指标当前未实现，因此不在本报告中给出猜测值。",
        ],
    )


def _metric_section(metrics: dict[str, RawMetric], metric_ids: list[str]) -> str:
    lines = []
    for metric_id in metric_ids:
        metric = metrics.get(metric_id)
        if metric is None:
            lines.append(f"- {metric_id}: 不可用，当前结果未包含该指标。")
        elif not metric.available:
            lines.append(f"- {metric_id}: 不可用，原因: {metric.reason or '未说明'}。")
        else:
            lines.append(f"- {metric_id}: {_format_metric(metric)}")
    return "\n".join(lines)


def _comparison_section(
    result: EvaluationResult,
    comparison_results: list[EvaluationResult],
) -> str:
    if not comparison_results:
        return "当前仅有一个评估结果，未进行横向对比。"
    lines = [
        f"当前结果 {result.request.waveform.name} 综合得分 {result.overall_score:.2f}。",
        "对比结果摘要:",
    ]
    for item in comparison_results:
        lines.append(f"- {item.request.waveform.name}: 综合得分 {item.overall_score:.2f}")
    return "\n".join(lines)


def _build_recommendations(
    result: EvaluationResult,
    metrics: dict[str, RawMetric],
) -> list[str]:
    available_axes = [
        axis for axis in result.axis_scores if axis.available and axis.score is not None
    ]
    recommendations: list[str] = []
    if available_axes:
        weakest = min(available_axes, key=lambda axis: axis.score or 0.0)
        recommendations.append(
            f"优先关注得分较低的维度“{weakest.name}”，并结合该维度底层指标定位约束来源。",
        )
    unavailable = [metric for metric in metrics.values() if not metric.available]
    if unavailable:
        recommendations.append(
            "存在不可用指标，建议补齐对应模型参数后再进行完整横向比较。",
        )
    if _metric_available(metrics, "anti_jamming.jammed_pd"):
        recommendations.append(
            "抗干扰建议仅基于当前宽带高斯噪声压制干扰模型解释，不应外推到欺骗干扰或窄带干扰。",
        )
    if _metric_available(metrics, "lpi.nominal_avg_psd_w_per_hz"):
        recommendations.append(
            "低截获相关建议应结合峰值功率、名义平均 PSD、占用带宽和任务约束共同判断。",
        )
    if not recommendations:
        recommendations.append("当前结果未显示明确弱项，可保留评分配置并开展更多波形对比。")
    return recommendations


def _default_assumptions(scoring_config: ScoringConfig | None) -> list[str]:
    scoring_text = (
        f"评分依赖配置 {scoring_config.config_name} 的归一化边界和权重。"
        if scoring_config is not None
        else "评分配置未随报告输入提供，报告仅解释结果中已有得分。"
    )
    return [
        "所有指标由 radar_eval_core 计算，报告服务不计算新雷达指标。",
        scoring_text,
        "报告基于复基带波形和当前 EvaluationResult 的结构化结果。",
    ]


def _default_limitations() -> list[str]:
    return [
        "未包含实测数据校核。",
        "未包含复杂杂波模型。",
        "未包含完整侦收机模型，因此不输出截获概率。",
        "未覆盖全部干扰类型。",
        "二维 PSLR / ISLR、CFAR 和 Swerling 目标模型未在当前版本实现。",
    ]


def _summary_sentence(result: EvaluationResult, axis_by_id: dict[str, AxisScore]) -> str:
    unavailable_axes = [axis.name for axis in axis_by_id.values() if not axis.available]
    suffix = (
        f" 不可用维度包括: {'、'.join(unavailable_axes)}。"
        if unavailable_axes
        else ""
    )
    return f"{result.request.waveform.name} 的综合得分为 {result.overall_score:.2f}。{suffix}"


def _axis_score_text(axis: AxisScore) -> str:
    if axis.available and axis.score is not None:
        return f"{axis.score:.2f}"
    return f"不可用，原因: {axis.reason or '未说明'}"


def _format_metric(metric: RawMetric) -> str:
    if metric.value is None:
        return "不可用"
    unit = f" {metric.unit}" if metric.unit else ""
    description = f"，{metric.description}" if metric.description else ""
    return f"{metric.value:.8g}{unit}{description}"


def _metric_available(metrics: dict[str, RawMetric], metric_id: str) -> bool:
    metric = metrics.get(metric_id)
    return bool(metric is not None and metric.available and metric.value is not None)


def _list_text(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _markdownish_to_html(text: str) -> str:
    lines = text.splitlines()
    html_lines: list[str] = []
    in_list = False
    for line in lines:
        if line.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{escape(line[2:])}</li>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if line.strip():
                html_lines.append(f"<p>{escape(line)}</p>")
    if in_list:
        html_lines.append("</ul>")
    return "\n".join(html_lines)
