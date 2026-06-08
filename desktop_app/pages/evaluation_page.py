"""评估执行页面。"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from desktop_app.app_state import AppState
from desktop_app.services.evaluation_service import EvaluationService, EvaluationServiceError
from desktop_app.workers.evaluation_worker import EvaluationWorker
from radar_eval_core.schemas import EvaluationResult


class EvaluationPage(QWidget):
    """运行算法评估的页面。"""

    evaluation_finished = Signal(object)
    switch_to_visualization = Signal()
    status_changed = Signal(str)

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        """初始化评估页面。"""
        super().__init__(parent)
        self._state = state
        self._service = EvaluationService()
        self._thread: QThread | None = None
        self._worker: EvaluationWorker | None = None
        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.start_button = QPushButton("开始评估")
        self.start_button.setObjectName("PrimaryButton")
        self.result_state_label = QLabel("尚未运行评估")
        self.result_state_label.setObjectName("PageSubtitle")
        self._build_layout()
        self.refresh_from_state()

    def refresh_from_state(self) -> None:
        """刷新请求摘要。"""
        request = self._state.current_request
        if request is None:
            self.summary.setPlainText("当前没有评估请求。")
        else:
            self.summary.setPlainText(
                json.dumps(request.model_dump(mode="json"), ensure_ascii=False, indent=2),
            )
        if self._state.current_result is None:
            self.result_state_label.setText("尚未运行评估")
        else:
            score = self._state.current_result.overall_score
            self.result_state_label.setText(f"最近一次评估完成，综合得分 {score:.2f}")

    def _build_layout(self) -> None:
        """构建运行评估页面布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(_header("运行评估", "后台调用算法评估流水线；界面不执行任何雷达公式。"))

        surface = QFrame()
        surface.setObjectName("PageSurface")
        surface_layout = QHBoxLayout(surface)
        surface_layout.setContentsMargins(18, 18, 18, 18)
        surface_layout.setSpacing(16)

        action_panel = QFrame()
        action_panel.setObjectName("SoftPanel")
        action_panel.setFixedWidth(280)
        action_layout = QVBoxLayout(action_panel)
        action_layout.setContentsMargins(14, 14, 14, 14)
        action_layout.setSpacing(10)
        action_title = QLabel("评估操作")
        action_title.setObjectName("SectionTitle")
        load_lfm_button = QPushButton("加载默认 LFM")
        load_phase_button = QPushButton("加载默认相位编码")
        save_result_button = QPushButton("保存结果 JSON")
        load_lfm_button.clicked.connect(lambda: self._load_request("configs/lfm_default.json"))
        load_phase_button.clicked.connect(
            lambda: self._load_request("configs/phase_code_default.json"),
        )
        self.start_button.clicked.connect(self.start_evaluation)
        save_result_button.clicked.connect(self._save_result)
        action_layout.addWidget(action_title)
        action_layout.addWidget(self.result_state_label)
        action_layout.addSpacing(8)
        action_layout.addWidget(load_lfm_button)
        action_layout.addWidget(load_phase_button)
        action_layout.addWidget(self.start_button)
        action_layout.addWidget(save_result_button)
        action_layout.addStretch(1)

        summary_panel = QFrame()
        summary_panel.setObjectName("SoftPanel")
        summary_layout = QVBoxLayout(summary_panel)
        summary_layout.setContentsMargins(14, 14, 14, 14)
        summary_layout.setSpacing(10)
        summary_title = QLabel("当前请求摘要")
        summary_title.setObjectName("SectionTitle")
        summary_layout.addWidget(summary_title)
        summary_layout.addWidget(self.summary)

        surface_layout.addWidget(action_panel)
        surface_layout.addWidget(summary_panel, stretch=1)
        layout.addWidget(surface, stretch=1)

    def start_evaluation(self) -> None:
        """创建后台 worker 并开始评估。"""
        if self._state.current_request is None:
            QMessageBox.warning(self, "无法评估", "当前没有 EvaluationRequest。")
            return
        if self._state.current_scoring_config is None:
            QMessageBox.warning(self, "无法评估", "当前没有 ScoringConfig。")
            return

        self.start_button.setEnabled(False)
        self.result_state_label.setText("正在评估，请稍候")
        self.status_changed.emit("正在评估")
        self._thread = QThread(self)
        self._worker = EvaluationWorker(
            self._state.current_request,
            self._state.current_scoring_config,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.failed.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _load_request(self, path_text: str) -> None:
        """加载默认请求和评分配置。"""
        try:
            self._state.current_request = self._service.load_request(Path(path_text))
            self._state.current_scoring_config = self._service.load_scoring_config(
                Path("configs/scoring_default.json"),
            )
            self._state.current_result = None
            self._state.dirty = True
            self.refresh_from_state()
            self.status_changed.emit(f"已加载 {path_text}")
        except EvaluationServiceError as exc:
            QMessageBox.critical(self, "加载失败", str(exc))

    def _on_finished(self, result: EvaluationResult) -> None:
        """处理评估完成。"""
        self._state.current_result = result
        self._state.dirty = True
        self.start_button.setEnabled(True)
        self.refresh_from_state()
        self.status_changed.emit("评估完成")
        self.evaluation_finished.emit(result)
        self.switch_to_visualization.emit()

    def _on_failed(self, message: str) -> None:
        """处理评估失败。"""
        self.start_button.setEnabled(True)
        self.result_state_label.setText("评估失败")
        self.status_changed.emit("评估失败")
        QMessageBox.critical(self, "评估失败", message)

    def _save_result(self) -> None:
        """保存当前 EvaluationResult。"""
        if self._state.current_result is None:
            QMessageBox.information(self, "没有结果", "当前没有可保存的评估结果。")
            return
        path_text, _ = QFileDialog.getSaveFileName(
            self,
            "保存评估结果",
            "evaluation_result.json",
            "JSON Files (*.json)",
        )
        if not path_text:
            return
        path = Path(path_text)
        with path.open("w", encoding="utf-8") as file:
            json.dump(
                self._state.current_result.model_dump(mode="json"),
                file,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            file.write("\n")


def create_evaluation_page(state: AppState | None = None) -> EvaluationPage:
    """兼容旧入口，创建评估执行页面。"""
    return EvaluationPage(state or AppState())


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

