"""综合评分卡组件。"""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from radar_eval_core.schemas import EvaluationResult


class ScoreCardWidget(QWidget):
    """展示总分和各维度得分。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化评分卡。"""
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)
        self.set_result(None)

    def set_result(self, result: EvaluationResult | None) -> None:
        """显示评估结果摘要。"""
        _clear_layout(self._layout)
        if result is None:
            empty = QLabel("暂无评分结果")
            empty.setObjectName("PageSubtitle")
            self._layout.addWidget(empty)
            return

        total = QLabel(f"{result.overall_score:.1f}")
        total.setStyleSheet("font-size: 34px; font-weight: 700; color: #0f766e;")
        title = QLabel("综合得分")
        title.setObjectName("PageSubtitle")
        self._layout.addWidget(title)
        self._layout.addWidget(total)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        for row, axis_score in enumerate(result.axis_scores):
            label = QLabel(axis_score.name)
            label.setMinimumWidth(90)
            value = (
                int(round(axis_score.score))
                if axis_score.available and axis_score.score is not None
                else 0
            )
            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(value)
            progress.setTextVisible(False)
            progress.setFixedHeight(8)
            text = QLabel(
                f"{axis_score.score:.1f}"
                if axis_score.available and axis_score.score is not None
                else "不可用",
            )
            text.setMinimumWidth(46)
            grid.addWidget(label, row, 0)
            grid.addWidget(progress, row, 1)
            grid.addWidget(text, row, 2)
        self._layout.addLayout(grid)
        self._layout.addStretch(1)


def _clear_layout(layout: QVBoxLayout | QGridLayout) -> None:
    """清空布局中的已有控件。"""
    while layout.count():
        item = layout.takeAt(0)
        child_layout = item.layout()
        widget = item.widget()
        if child_layout is not None:
            _clear_layout(child_layout)
        if widget is not None:
            widget.deleteLater()
