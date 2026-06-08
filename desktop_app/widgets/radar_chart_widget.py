"""雷达图展示组件。"""

from __future__ import annotations

import math
from collections.abc import Sequence

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtWidgets import QVBoxLayout, QWidget

from radar_eval_core.schemas import AxisScore, EvaluationResult


class RadarChartWidget(QWidget):
    """使用 matplotlib 绘制单结果或多结果雷达图。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化雷达图组件。"""
        super().__init__(parent)
        self._figure = Figure(figsize=(4.4, 3.4), facecolor="#ffffff")
        self._canvas = FigureCanvas(self._figure)
        layout = QVBoxLayout(self)
        layout.addWidget(self._canvas)
        self.set_results([])

    def set_axis_scores(self, axis_scores: Sequence[AxisScore]) -> None:
        """显示单个结果的 axis score。"""
        self._plot([("当前结果", axis_scores)])

    def set_results(self, results: Sequence[EvaluationResult]) -> None:
        """显示多个评估结果的 axis score 叠加。"""
        series = [
            (result.request.waveform.name or f"结果 {index + 1}", result.axis_scores)
            for index, result in enumerate(results)
        ]
        self._plot(series)

    def _plot(self, series: Sequence[tuple[str, Sequence[AxisScore]]]) -> None:
        """绘制雷达图。"""
        self._figure.clear()
        axis = self._figure.add_subplot(111, polar=True)
        axis.set_facecolor("#ffffff")
        if not series:
            axis.text(
                0.5,
                0.5,
                "No radar chart data",
                ha="center",
                va="center",
                transform=axis.transAxes,
            )
            axis.set_axis_off()
            self._canvas.draw_idle()
            return

        labels = [score.name for score in series[0][1]]
        if not labels:
            axis.text(
                0.5,
                0.5,
                "No axis scores",
                ha="center",
                va="center",
                transform=axis.transAxes,
            )
            axis.set_axis_off()
            self._canvas.draw_idle()
            return

        angles = [2 * math.pi * index / len(labels) for index in range(len(labels))]
        angles.append(angles[0])
        colors = ["#0f766e", "#3b82f6", "#b45309", "#7c3aed", "#be123c"]
        for index, (label, scores) in enumerate(series):
            values = [
                score.score if score.available and score.score is not None else 0.0
                for score in scores
            ]
            values.append(values[0])
            color = colors[index % len(colors)]
            axis.plot(angles, values, linewidth=1.8, label=label, color=color)
            axis.fill(angles, values, alpha=0.08, color=color)

        axis.set_xticks(angles[:-1])
        axis.set_xticklabels(labels, fontsize=8)
        axis.set_ylim(0, 100)
        axis.set_yticks([20, 40, 60, 80, 100])
        axis.grid(color="#d7dee6", linewidth=0.8)
        if len(series) > 1:
            axis.legend(loc="upper right", bbox_to_anchor=(1.22, 1.12), fontsize=8)
        self._figure.tight_layout()
        self._canvas.draw_idle()


def create_radar_chart_widget() -> RadarChartWidget:
    """兼容旧入口，创建雷达图组件。"""
    return RadarChartWidget()
