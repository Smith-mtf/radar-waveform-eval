"""指标表格组件。"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from radar_eval_core.schemas import RawMetric


class MetricTableWidget(QTableWidget):
    """展示 EvaluationResult.raw_metrics 的表格。"""

    _HEADERS = [
        "metric_id",
        "display_name",
        "raw_value",
        "unit",
        "score",
        "axis_id",
        "available",
        "unavailable_reason",
    ]

    def __init__(self, parent=None) -> None:
        """初始化指标表格。"""
        super().__init__(parent)
        self.setColumnCount(len(self._HEADERS))
        self.setHorizontalHeaderLabels(self._HEADERS)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.setWordWrap(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    def set_metrics(self, metrics: Sequence[RawMetric], axis_filter: str | None = None) -> None:
        """设置要展示的指标，可按 axis_id 过滤。"""
        self.setSortingEnabled(False)
        filtered = [
            metric
            for metric in metrics
            if axis_filter is None or metric.axis_id == axis_filter
        ]
        self.setRowCount(len(filtered))
        for row, metric in enumerate(filtered):
            score = getattr(metric, "score", "")
            values = [
                metric.metric_id,
                metric.description,
                "" if metric.value is None else f"{metric.value:.8g}",
                metric.unit,
                "" if score is None else str(score),
                metric.axis_id,
                "是" if metric.available else "否",
                metric.reason or "",
            ]
            for column, value in enumerate(values):
                self.setItem(row, column, QTableWidgetItem(value))
        self.setSortingEnabled(True)


def create_metric_table_widget() -> MetricTableWidget:
    """兼容旧入口，创建指标表格组件。"""
    return MetricTableWidget()

