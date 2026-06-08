"""评估报告页面。"""

from __future__ import annotations

from pathlib import Path

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
from desktop_app.services.export_service import (
    ExportServiceError,
    export_report_html,
    export_report_markdown,
)
from desktop_app.services.report_service import (
    ReportDocument,
    generate_local_template_report,
    render_report_html,
    render_report_markdown,
)


class ReportPage(QWidget):
    """显示本地模板报告，不调用大模型 API。"""

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        """初始化报告页面。"""
        super().__init__(parent)
        self._state = state
        self._report: ReportDocument | None = None
        self._markdown = ""
        self._html = ""
        self.generated_at_label = QLabel("尚未生成报告")
        self.generated_at_label.setObjectName("PageSubtitle")
        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self._build_layout()
        self.refresh_from_state()

    def refresh_from_state(self) -> None:
        """刷新报告页状态。"""
        if self._state.current_result is None:
            self._report = None
            self._markdown = ""
            self._html = ""
            self.generated_at_label.setText("请先运行评估")
            self.summary.setPlainText("暂无评估结果。请先在“运行评估”页完成一次评估。")
            return
        if self._report is None:
            self.generated_at_label.setText("可生成本地模板报告")
            self.summary.setPlainText("当前评估结果已就绪，点击“生成本地报告”生成正文。")

    def _build_layout(self) -> None:
        """构建报告页面布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(
            _header("评估报告", "本地模板报告只解释已有 EvaluationResult，不调用外部 LLM。"),
        )

        surface = QFrame()
        surface.setObjectName("PageSurface")
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(18, 18, 18, 18)
        surface_layout.setSpacing(12)

        action_layout = QHBoxLayout()
        generate_button = QPushButton("生成本地报告")
        export_md_button = QPushButton("导出 Markdown")
        export_html_button = QPushButton("导出 HTML")
        generate_button.setObjectName("PrimaryButton")
        generate_button.clicked.connect(self._generate_report)
        export_md_button.clicked.connect(self._export_markdown)
        export_html_button.clicked.connect(self._export_html)
        action_layout.addWidget(self.generated_at_label)
        action_layout.addStretch(1)
        action_layout.addWidget(generate_button)
        action_layout.addWidget(export_md_button)
        action_layout.addWidget(export_html_button)

        surface_layout.addLayout(action_layout)
        surface_layout.addWidget(self.summary)
        layout.addWidget(surface, stretch=1)

    def _generate_report(self) -> None:
        """生成本地模板报告。"""
        result = self._state.current_result
        if result is None:
            QMessageBox.information(self, "没有结果", "请先运行评估。")
            return
        self._report = generate_local_template_report(
            result,
            scoring_config=self._state.current_scoring_config,
            comparison_results=self._state.comparison_results,
        )
        self._markdown = render_report_markdown(self._report)
        self._html = render_report_html(self._report)
        self.generated_at_label.setText(f"生成时间: {self._report.generated_at}")
        self.summary.setPlainText(self._markdown)

    def _export_markdown(self) -> None:
        """导出 Markdown 报告。"""
        if not self._ensure_report():
            return
        path_text, _ = QFileDialog.getSaveFileName(
            self,
            "导出 Markdown 报告",
            "report.md",
            "Markdown Files (*.md)",
        )
        if not path_text:
            return
        try:
            export_report_markdown(self._markdown, Path(path_text))
        except ExportServiceError as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        QMessageBox.information(self, "导出成功", f"已保存到 {path_text}")

    def _export_html(self) -> None:
        """导出 HTML 报告。"""
        if not self._ensure_report():
            return
        path_text, _ = QFileDialog.getSaveFileName(
            self,
            "导出 HTML 报告",
            "report.html",
            "HTML Files (*.html)",
        )
        if not path_text:
            return
        try:
            export_report_html(self._html, Path(path_text))
        except ExportServiceError as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        QMessageBox.information(self, "导出成功", f"已保存到 {path_text}")

    def _ensure_report(self) -> bool:
        """确保已有可导出的报告正文。"""
        if self._state.current_result is None:
            QMessageBox.information(self, "没有结果", "请先运行评估。")
            return False
        if self._report is None:
            self._generate_report()
        return self._report is not None


def create_report_page(state: AppState | None = None) -> ReportPage:
    """兼容旧入口，创建报告页面。"""
    return ReportPage(state or AppState())


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
