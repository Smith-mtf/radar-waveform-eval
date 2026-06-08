"""横向对比页面。"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop_app.app_state import AppState
from desktop_app.widgets.radar_chart_widget import RadarChartWidget
from radar_eval_core.schemas import EvaluationResult


class ComparisonPage(QWidget):
    """展示多个 EvaluationResult 横向对比。"""

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        """初始化横向对比页面。"""
        super().__init__(parent)
        self._state = state
        self.warning_label = QLabel("不同结果可能使用了不同评分配置，横向对比仅供参考。")
        self.warning_label.setObjectName("PageSubtitle")
        self.radar_chart = RadarChartWidget()
        self.ranking_table = QTableWidget()
        self.axis_table = QTableWidget()
        self._setup_table(self.ranking_table)
        self._setup_table(self.axis_table)
        self._build_layout()
        self.refresh_from_state()

    def refresh_from_state(self) -> None:
        """刷新对比结果。"""
        results = self._state.comparison_results
        self.radar_chart.set_results(results)
        self._fill_ranking_table(results)
        self._fill_axis_table(results)

    def _build_layout(self) -> None:
        """构建横向对比布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(_header("横向对比", "只比较已有评估结果，不重新计算指标。"))
        layout.addWidget(self.warning_label)

        surface = QFrame()
        surface.setObjectName("PageSurface")
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(18, 18, 18, 18)
        surface_layout.setSpacing(16)

        button_layout = QHBoxLayout()
        add_button = QPushButton("添加当前结果")
        import_button = QPushButton("导入 evaluation_result.json")
        add_button.clicked.connect(self._add_current_result)
        import_button.clicked.connect(self._import_result)
        button_layout.addStretch(1)
        button_layout.addWidget(add_button)
        button_layout.addWidget(import_button)

        table_row = QHBoxLayout()
        table_row.setSpacing(16)
        table_row.addWidget(_panel("综合得分排名", self.ranking_table), stretch=1)
        table_row.addWidget(_panel("六维得分对比", self.axis_table), stretch=2)

        surface_layout.addLayout(button_layout)
        surface_layout.addWidget(_panel("多结果雷达图", self.radar_chart), stretch=2)
        surface_layout.addLayout(table_row, stretch=1)
        layout.addWidget(surface, stretch=1)

    def _add_current_result(self) -> None:
        """将当前结果加入对比列表。"""
        if self._state.current_result is None:
            QMessageBox.information(self, "没有结果", "当前没有可加入对比的评估结果。")
            return
        self._state.comparison_results.append(self._state.current_result)
        self._state.dirty = True
        self.refresh_from_state()

    def _import_result(self) -> None:
        """导入历史 evaluation_result.json。"""
        path_text, _ = QFileDialog.getOpenFileName(
            self,
            "导入评估结果",
            "",
            "JSON Files (*.json)",
        )
        if not path_text:
            return
        try:
            payload = json.loads(Path(path_text).read_text(encoding="utf-8"))
            result = EvaluationResult.model_validate(payload)
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", str(exc))
            return
        self._state.comparison_results.append(result)
        self._state.dirty = True
        self.refresh_from_state()

    def _fill_ranking_table(self, results: list[EvaluationResult]) -> None:
        """填充综合得分排名表。"""
        ranked = sorted(results, key=lambda item: item.overall_score, reverse=True)
        self.ranking_table.setColumnCount(3)
        self.ranking_table.setHorizontalHeaderLabels(["排名", "波形名称", "总分"])
        self.ranking_table.setRowCount(len(ranked))
        for row, result in enumerate(ranked):
            values = [str(row + 1), result.request.waveform.name, f"{result.overall_score:.2f}"]
            for column, value in enumerate(values):
                self.ranking_table.setItem(row, column, QTableWidgetItem(value))

    def _fill_axis_table(self, results: list[EvaluationResult]) -> None:
        """填充 6 维得分对比表。"""
        axis_ids = [
            "detection",
            "resolution",
            "sidelobe_ambiguity",
            "anti_jamming",
            "lpi",
            "engineering",
        ]
        self.axis_table.setColumnCount(1 + len(axis_ids))
        self.axis_table.setHorizontalHeaderLabels(["波形名称", *axis_ids])
        self.axis_table.setRowCount(len(results))
        for row, result in enumerate(results):
            self.axis_table.setItem(row, 0, QTableWidgetItem(result.request.waveform.name))
            axis_by_id = {axis.axis_id: axis for axis in result.axis_scores}
            for column, axis_id in enumerate(axis_ids, start=1):
                axis = axis_by_id.get(axis_id)
                text = (
                    f"{axis.score:.2f}"
                    if axis is not None and axis.available and axis.score is not None
                    else "不可用"
                )
                self.axis_table.setItem(row, column, QTableWidgetItem(text))

    @staticmethod
    def _setup_table(table: QTableWidget) -> None:
        """设置对比表格的统一行为。"""
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)


def create_comparison_page(state: AppState | None = None) -> ComparisonPage:
    """兼容旧入口，创建方案对比页面。"""
    return ComparisonPage(state or AppState())


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
