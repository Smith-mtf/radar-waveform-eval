"""主窗口定义。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from desktop_app.app_state import AppState
from desktop_app.pages.comparison_page import ComparisonPage
from desktop_app.pages.evaluation_page import EvaluationPage
from desktop_app.pages.report_page import ReportPage
from desktop_app.pages.scenario_page import ScenarioPage
from desktop_app.pages.visualization_page import VisualizationPage
from desktop_app.pages.waveform_page import WaveformPage
from desktop_app.services.evaluation_service import EvaluationService
from desktop_app.services.export_service import (
    ExportServiceError,
    export_axis_scores_csv,
    export_chart_data_json,
    export_evaluation_json,
    export_raw_metrics_csv,
    export_report_html,
    export_report_markdown,
)
from desktop_app.services.project_service import ProjectService, ProjectServiceError
from desktop_app.services.report_service import (
    generate_local_template_report,
    render_report_html,
    render_report_markdown,
)
from desktop_app.version import APP_NAME, APP_STAGE, APP_VERSION
from radar_eval_core.schemas import EvaluationRequest, EvaluationResult


class MainWindow(QMainWindow):
    """雷达波形性能评估软件主窗口。"""

    def __init__(self, state: AppState | None = None) -> None:
        """初始化主窗口、导航、菜单和状态栏。"""
        super().__init__()
        self._state = state or AppState(current_request=EvaluationRequest())
        self._project_service = ProjectService()
        self._evaluation_service = EvaluationService()
        self._status_label = QLabel("就绪")
        self._project_label = QLabel("项目: 未保存")
        self._navigation = QListWidget()
        self._stack = QStackedWidget()
        self._pages: list[Any] = []

        self.setWindowTitle(f"{APP_NAME} V1.0")
        self.setMinimumSize(1180, 760)
        self.resize(1320, 860)
        self._build_pages()
        self._build_central_widget()
        self._build_menu()
        self._build_status_bar()
        self.refresh_all_pages()

    def refresh_all_pages(self) -> None:
        """刷新所有页面和状态栏。"""
        for page in self._pages:
            refresh = getattr(page, "refresh_from_state", None)
            if callable(refresh):
                refresh()
        self._project_label.setText(
            "项目: 未保存"
            if self._state.current_project_path is None
            else f"项目: {self._state.current_project_path}",
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        """退出前检查未保存状态。"""
        if self._confirm_discard_or_save():
            event.accept()
        else:
            event.ignore()

    def _build_pages(self) -> None:
        """创建页面实例。"""
        self.waveform_page = WaveformPage(self._state)
        self.scenario_page = ScenarioPage(self._state)
        self.evaluation_page = EvaluationPage(self._state)
        self.visualization_page = VisualizationPage(self._state)
        self.comparison_page = ComparisonPage(self._state)
        self.report_page = ReportPage(self._state)
        self.evaluation_page.evaluation_finished.connect(self._on_evaluation_finished)
        self.evaluation_page.switch_to_visualization.connect(lambda: self._set_page_index(3))
        self.evaluation_page.status_changed.connect(self._set_status)
        self._pages = [
            self.waveform_page,
            self.scenario_page,
            self.evaluation_page,
            self.visualization_page,
            self.comparison_page,
            self.report_page,
        ]

    def _build_central_widget(self) -> None:
        """构建左侧导航和右侧页面区域。"""
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        for page in self._pages:
            self._stack.addWidget(page)
        root_layout.addWidget(self._build_sidebar())
        root_layout.addWidget(self._stack, stretch=1)
        self.setCentralWidget(root)
        self._set_page_index(0)

    def _build_sidebar(self) -> QFrame:
        """构建工作台导航。"""
        sidebar = QFrame()
        sidebar.setObjectName("AppSidebar")
        sidebar.setFixedWidth(244)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(12)

        title = QLabel("雷达波形评估")
        title.setObjectName("AppTitle")
        subtitle = QLabel("V1.0 算法评估工作台")
        subtitle.setObjectName("AppSubtitle")
        self._navigation.setObjectName("NavigationList")
        self._navigation.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._navigation.addItems(
            ["波形配置", "场景配置", "运行评估", "结果可视化", "横向对比", "评估报告"],
        )
        self._navigation.currentRowChanged.connect(self._stack.setCurrentIndex)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        layout.addWidget(self._navigation)
        layout.addStretch(1)
        return sidebar

    def _build_menu(self) -> None:
        """构建菜单栏。"""
        file_menu = self.menuBar().addMenu("文件")
        file_menu.addAction(_action(self, "新建项目", self._new_project))
        file_menu.addAction(_action(self, "打开项目", self._open_project))
        file_menu.addAction(_action(self, "保存项目", self._save_project))
        file_menu.addSeparator()
        file_menu.addAction(_action(self, "导出完整评估 JSON", self._export_evaluation_json))
        file_menu.addAction(_action(self, "导出原始指标 CSV", self._export_raw_metrics_csv))
        file_menu.addAction(_action(self, "导出评分 CSV", self._export_axis_scores_csv))
        file_menu.addAction(_action(self, "导出图表数据 JSON", self._export_chart_data_json))
        file_menu.addSeparator()
        file_menu.addAction(_action(self, "导出报告 Markdown", self._export_report_markdown))
        file_menu.addAction(_action(self, "导出报告 HTML", self._export_report_html))
        file_menu.addSeparator()
        file_menu.addAction(_action(self, "退出", self.close))

        evaluation_menu = self.menuBar().addMenu("评估")
        evaluation_menu.addAction(_action(self, "开始评估", self.evaluation_page.start_evaluation))

        help_menu = self.menuBar().addMenu("帮助")
        help_menu.addAction(_action(self, "关于", self._show_about))

    def _build_status_bar(self) -> None:
        """构建状态栏。"""
        self.statusBar().addPermanentWidget(self._project_label, stretch=1)
        self.statusBar().addPermanentWidget(self._status_label)

    def _new_project(self) -> None:
        """创建新项目。"""
        if not self._confirm_discard_or_save():
            return
        self._state.current_project_path = None
        self._state.current_request = EvaluationRequest()
        try:
            self._state.current_scoring_config = self._evaluation_service.load_scoring_config(
                Path("configs/scoring_default.json"),
            )
        except Exception:
            self._state.current_scoring_config = None
        self._state.current_result = None
        self._state.comparison_results.clear()
        self._state.dirty = False
        self._set_status("已新建项目")
        self.refresh_all_pages()

    def _open_project(self) -> None:
        """打开项目文件。"""
        if not self._confirm_discard_or_save():
            return
        path_text, _ = QFileDialog.getOpenFileName(
            self,
            "打开项目",
            "",
            "Radar Waveform Eval Project (*.rwep.json);;JSON Files (*.json)",
        )
        if not path_text:
            return
        try:
            loaded_state = self._project_service.open_project(Path(path_text))
        except ProjectServiceError as exc:
            QMessageBox.critical(self, "打开失败", str(exc))
            return
        self._state.current_project_path = loaded_state.current_project_path
        self._state.current_request = loaded_state.current_request
        self._state.current_scoring_config = loaded_state.current_scoring_config
        self._state.current_result = loaded_state.current_result
        self._state.comparison_results = loaded_state.comparison_results
        self._state.dirty = False
        self._set_status("项目已打开")
        self.refresh_all_pages()

    def _save_project(self) -> bool:
        """保存项目文件。"""
        path = self._state.current_project_path
        if path is None:
            path_text, _ = QFileDialog.getSaveFileName(
                self,
                "保存项目",
                "project.rwep.json",
                "Radar Waveform Eval Project (*.rwep.json)",
            )
            if not path_text:
                return False
            path = Path(path_text)
        try:
            self._project_service.save_project(self._state, path)
        except ProjectServiceError as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return False
        self._set_status("项目已保存")
        self.refresh_all_pages()
        return True

    def _export_evaluation_json(self) -> None:
        """导出完整评估 JSON。"""
        self._export_result_file(
            "导出完整评估 JSON",
            "evaluation_result.json",
            "JSON Files (*.json)",
            export_evaluation_json,
        )

    def _export_raw_metrics_csv(self) -> None:
        """导出原始指标 CSV。"""
        self._export_result_file(
            "导出原始指标 CSV",
            "raw_metrics.csv",
            "CSV Files (*.csv)",
            export_raw_metrics_csv,
        )

    def _export_axis_scores_csv(self) -> None:
        """导出评分 CSV。"""
        self._export_result_file(
            "导出评分 CSV",
            "axis_scores.csv",
            "CSV Files (*.csv)",
            export_axis_scores_csv,
        )

    def _export_chart_data_json(self) -> None:
        """导出图表数据 JSON。"""
        self._export_result_file(
            "导出图表数据 JSON",
            "chart_data.json",
            "JSON Files (*.json)",
            export_chart_data_json,
        )

    def _export_report_markdown(self) -> None:
        """导出 Markdown 报告。"""
        result = self._require_result()
        if result is None:
            return
        path_text, _ = QFileDialog.getSaveFileName(
            self,
            "导出报告 Markdown",
            "report.md",
            "Markdown Files (*.md)",
        )
        if not path_text:
            return
        report = generate_local_template_report(
            result,
            scoring_config=self._state.current_scoring_config,
            comparison_results=self._state.comparison_results,
        )
        try:
            export_report_markdown(render_report_markdown(report), Path(path_text))
        except ExportServiceError as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        self._set_status(f"已导出 {path_text}")

    def _export_report_html(self) -> None:
        """导出 HTML 报告。"""
        result = self._require_result()
        if result is None:
            return
        path_text, _ = QFileDialog.getSaveFileName(
            self,
            "导出报告 HTML",
            "report.html",
            "HTML Files (*.html)",
        )
        if not path_text:
            return
        report = generate_local_template_report(
            result,
            scoring_config=self._state.current_scoring_config,
            comparison_results=self._state.comparison_results,
        )
        try:
            export_report_html(render_report_html(report), Path(path_text))
        except ExportServiceError as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        self._set_status(f"已导出 {path_text}")

    def _export_result_file(
        self,
        title: str,
        default_name: str,
        file_filter: str,
        exporter: Callable[[EvaluationResult, Path], None],
    ) -> None:
        """导出当前 EvaluationResult 的某类文件。"""
        result = self._require_result()
        if result is None:
            return
        path_text, _ = QFileDialog.getSaveFileName(self, title, default_name, file_filter)
        if not path_text:
            return
        try:
            exporter(result, Path(path_text))
        except ExportServiceError as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        self._set_status(f"已导出 {path_text}")

    def _require_result(self) -> EvaluationResult | None:
        """获取当前结果；不存在时提示用户先运行评估。"""
        if self._state.current_result is None:
            QMessageBox.information(self, "没有评估结果", "请先运行评估。")
            return None
        return self._state.current_result

    def _confirm_discard_or_save(self) -> bool:
        """如果有未保存修改，询问保存、放弃或取消。"""
        if not self._state.dirty:
            return True
        reply = QMessageBox.question(
            self,
            "未保存修改",
            "当前项目有未保存修改，是否保存？",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if reply == QMessageBox.StandardButton.Save:
            return self._save_project()
        if reply == QMessageBox.StandardButton.Discard:
            return True
        return False

    def _on_evaluation_finished(self, _result: object) -> None:
        """评估完成后刷新结果页。"""
        self.refresh_all_pages()

    def _set_page_index(self, index: int) -> None:
        """切换页面。"""
        if self._navigation.currentRow() != index:
            self._navigation.setCurrentRow(index)
        self._stack.setCurrentIndex(index)

    def _set_status(self, text: str) -> None:
        """更新评估状态。"""
        self._status_label.setText(text)

    def _show_about(self) -> None:
        """显示关于信息。"""
        QMessageBox.information(
            self,
            "关于",
            "\n".join(
                [
                    f"{APP_NAME} {APP_VERSION}",
                    APP_STAGE,
                    "",
                    "技术栈: Python 3.12, PySide6 / QtWidgets, NumPy, SciPy, "
                    "Matplotlib, Pydantic。",
                    "当前功能: 波形评估、六维评分、图表展示、本地报告、"
                    "JSON/CSV/Markdown/HTML 导出。",
                    "当前限制: 不含外部 API、数据库、截获概率、CFAR、Swerling 和复杂干扰模型。",
                ],
            ),
        )


def _action(parent: QMainWindow, text: str, slot: Callable[[], Any]) -> QAction:
    """创建菜单 QAction。"""
    action = QAction(text, parent)
    action.triggered.connect(lambda _checked=False: slot())
    return action
