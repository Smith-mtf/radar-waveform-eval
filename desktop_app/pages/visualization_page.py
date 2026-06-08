"""结果可视化页面。"""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from desktop_app.app_state import AppState
from desktop_app.widgets.ambiguity_widget import AmbiguityWidget
from desktop_app.widgets.metric_table_widget import MetricTableWidget
from desktop_app.widgets.radar_chart_widget import RadarChartWidget
from desktop_app.widgets.score_card_widget import ScoreCardWidget
from desktop_app.widgets.spectrum_widget import SpectrumWidget
from radar_eval_core.schemas import EvaluationResult


class VisualizationPage(QWidget):
    """展示 EvaluationResult 的页面。"""

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        """初始化结果可视化页面。"""
        super().__init__(parent)
        self._state = state
        self.score_card = ScoreCardWidget()
        self.radar_chart = RadarChartWidget()
        self.metric_table = MetricTableWidget()
        self.ambiguity_widget = AmbiguityWidget()
        self.spectrum_widget = SpectrumWidget()
        self.json_preview = QTextEdit()
        self.json_preview.setReadOnly(True)
        self.json_preview.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.empty_label = QLabel("暂无评估结果。请先在“运行评估”页开始一次评估。")
        self.empty_label.setObjectName("PageSubtitle")
        self._build_layout()
        self.refresh_from_state()

    def refresh_from_state(self) -> None:
        """刷新当前评估结果展示。"""
        self.set_result(self._state.current_result)

    def set_result(self, result: EvaluationResult | None) -> None:
        """展示指定 EvaluationResult。"""
        self.empty_label.setVisible(result is None)
        self.score_card.set_result(result)
        if result is None:
            self.radar_chart.set_results([])
            self.metric_table.set_metrics([])
            self.ambiguity_widget.set_chart_data({})
            self.spectrum_widget.set_chart_data({})
            self.json_preview.setPlainText("")
            return

        self.radar_chart.set_axis_scores(result.axis_scores)
        self.metric_table.set_metrics(result.raw_metrics)
        self.ambiguity_widget.set_chart_data(result.chart_data)
        self.spectrum_widget.set_chart_data(result.chart_data)
        self.json_preview.setPlainText(
            json.dumps(result.chart_data, ensure_ascii=False, indent=2),
        )

    def _build_layout(self) -> None:
        """构建集中式结果工作台布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(_header("结果可视化", "展示评估流水线返回的结构化结果和图表数据。"))
        layout.addWidget(self.empty_label)

        surface = QFrame()
        surface.setObjectName("PageSurface")
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(18, 18, 18, 18)
        surface_layout.setSpacing(16)

        top_row = QHBoxLayout()
        top_row.setSpacing(16)
        top_row.addWidget(_panel("综合评分", self.score_card), stretch=1)
        top_row.addWidget(_panel("六维雷达图", self.radar_chart), stretch=1)

        chart_row = QHBoxLayout()
        chart_row.setSpacing(16)
        chart_row.addWidget(_panel("模糊函数", self.ambiguity_widget), stretch=1)
        chart_row.addWidget(_panel("频谱 PSD", self.spectrum_widget), stretch=1)

        details = QTabWidget()
        details.addTab(self.metric_table, "底层指标")
        details.addTab(self.json_preview, "chart_data JSON")

        surface_layout.addLayout(top_row, stretch=1)
        surface_layout.addLayout(chart_row, stretch=1)
        surface_layout.addWidget(details, stretch=2)
        layout.addWidget(surface, stretch=1)


def create_visualization_page(state: AppState | None = None) -> VisualizationPage:
    """兼容旧入口，创建结果可视化页面。"""
    return VisualizationPage(state or AppState())


def _header(title: str, subtitle: str) -> QWidget:
    header = QWidget()
    layout = QVBoxLayout(header)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    title_label = QLabel(title)
    title_label.setObjectName("PageTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("PageSubtitle")
    layout.addWidget(title_label)
    layout.addWidget(subtitle_label)
    return header


def _panel(title: str, content: QWidget) -> QFrame:
    panel = QFrame()
    panel.setObjectName("SoftPanel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(12, 10, 12, 12)
    layout.setSpacing(8)
    title_label = QLabel(title)
    title_label.setObjectName("SectionTitle")
    layout.addWidget(title_label)
    layout.addWidget(content, stretch=1)
    return panel

