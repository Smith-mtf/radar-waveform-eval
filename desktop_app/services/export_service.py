"""本地导出服务。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from radar_eval_core.schemas import EvaluationResult


class ExportServiceError(RuntimeError):
    """导出服务错误。"""


def export_evaluation_json(result: EvaluationResult, path: Path) -> None:
    """导出完整 evaluation_result.json。"""
    _write_text(
        path,
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2, allow_nan=False)
        + "\n",
    )


def export_raw_metrics_csv(result: EvaluationResult, path: Path) -> None:
    """导出原始指标 CSV。"""
    rows = [
        {
            "metric_id": metric.metric_id,
            "display_name": metric.description,
            "raw_value": "" if metric.value is None else f"{metric.value:.12g}",
            "unit": metric.unit,
            "score": "",
            "axis_id": metric.axis_id,
            "available": str(metric.available).lower(),
            "unavailable_reason": metric.reason or "",
        }
        for metric in result.raw_metrics
    ]
    _write_csv(
        path,
        [
            "metric_id",
            "display_name",
            "raw_value",
            "unit",
            "score",
            "axis_id",
            "available",
            "unavailable_reason",
        ],
        rows,
    )


def export_axis_scores_csv(result: EvaluationResult, path: Path) -> None:
    """导出维度评分 CSV。"""
    rows = [
        {
            "axis_id": axis.axis_id,
            "display_name": axis.name,
            "score": "" if axis.score is None else f"{axis.score:.12g}",
            "weight": "",
            "available": str(axis.available).lower(),
            "unavailable_reason": axis.reason or "",
        }
        for axis in result.axis_scores
    ]
    _write_csv(
        path,
        ["axis_id", "display_name", "score", "weight", "available", "unavailable_reason"],
        rows,
    )


def export_chart_data_json(result: EvaluationResult, path: Path) -> None:
    """导出 chart_data.json。"""
    _write_text(
        path,
        json.dumps(result.chart_data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
    )


def export_report_markdown(markdown: str, path: Path) -> None:
    """导出 Markdown 报告。"""
    _write_text(path, markdown)


def export_report_html(html: str, path: Path) -> None:
    """导出 HTML 报告。"""
    _write_text(path, html)

def _write_text(path: Path, content: str) -> None:
    """写入 UTF-8 文本文件，并包装路径错误。"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except Exception as exc:
        raise ExportServiceError(f"导出文件失败: {path}: {exc}") from exc


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    """写入 UTF-8 CSV 文件，并包装路径错误。"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    except Exception as exc:
        raise ExportServiceError(f"导出 CSV 失败: {path}: {exc}") from exc
