"""雷达波形性能评估软件主界面。"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from desktop_app.app_state import AppState
from desktop_app.services.evaluation_service import EvaluationService, EvaluationServiceError
from desktop_app.services.export_service import (
    ExportServiceError,
    export_evaluation_json,
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
from desktop_app.workers.evaluation_worker import EvaluationWorker
from radar_eval_core.schemas import (
    EvaluationRequest,
    EvaluationResult,
    EvaluationSettings,
    JammerConfig,
    RawMetric,
    ScenarioConfig,
    WaveformConfig,
)
from radar_eval_core.scoring import ScoringConfig

try:
    import pyqtgraph as pg  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - 依赖同步前允许导入主窗口
    pg = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REQUEST_PATH = PROJECT_ROOT / "configs" / "lfm_default.json"
DEFAULT_PHASE_CODE_PATH = PROJECT_ROOT / "configs" / "phase_code_default.json"
DEFAULT_SCORING_PATH = PROJECT_ROOT / "configs" / "scoring_default.json"


SHELL_QSS = """
QFrame#TopBar {
    background: #0b1220;
    border-bottom: 1px solid #243244;
}
QLabel#ShellTitle {
    color: #f8fafc;
    font-size: 18px;
    font-weight: 800;
}
QLabel#ShellState {
    color: #bae6fd;
    padding: 0 8px;
}
QFrame#LeftPanel {
    background: #0f172a;
    border-right: 1px solid #243244;
}
QLabel#Breadcrumb {
    background: #132033;
    border: 1px solid #2f3f55;
    border-radius: 8px;
    color: #dbeafe;
    padding: 9px 12px;
}
QFrame#ChartFrame, QFrame#MetricCard, QFrame#PreviewTextFrame {
    background: #111827;
    border: 1px solid #2f3f55;
    border-radius: 8px;
}
QLabel#ScoreValue {
    color: #67e8f9;
    font-size: 34px;
    font-weight: 900;
}
QLabel#MetricCardTitle {
    color: #93a4b8;
}
QLabel#MetricCardValue {
    color: #f8fafc;
    font-size: 18px;
    font-weight: 800;
}
QPushButton#RunButton {
    min-height: 40px;
    background: #2563eb;
    border: 1px solid #3b82f6;
    border-radius: 7px;
    color: #ffffff;
    font-size: 14px;
    font-weight: 800;
}
QPushButton#RunButton:hover {
    background: #1d4ed8;
}
QPushButton#ExportButton {
    background: #0891b2;
    border: 1px solid #22d3ee;
    color: #ffffff;
    font-weight: 800;
}
"""


class TopBar(QFrame):
    """顶部标题栏和常用操作区。"""

    def __init__(self) -> None:
        """创建标题、状态提示和常用按钮。"""
        super().__init__()
        self.setObjectName("TopBar")
        self.status_label = QLabel("当前状态：就绪")
        self.status_label.setObjectName("ShellState")
        self.load_default_button = QPushButton("加载默认配置")
        self.export_report_button = QPushButton("导出报告")
        self.export_report_button.setObjectName("ExportButton")

        title = QLabel(f"{APP_NAME} V1.0")
        title.setObjectName("ShellTitle")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(self.status_label)
        layout.addWidget(self.load_default_button)
        layout.addWidget(self.export_report_button)

    def set_status(self, text: str) -> None:
        """更新顶部状态提示。"""
        self.status_label.setText(f"当前状态：{text}")


class LeftParameterPanel(QFrame):
    """左侧参数控制面板。"""

    start_requested = Signal()

    def __init__(self) -> None:
        """创建滚动参数区和底部常驻评估按钮。"""
        super().__init__()
        self.setObjectName("LeftPanel")
        self._build_controls()

    def load_from_request(self, request: EvaluationRequest) -> None:
        """将 EvaluationRequest 的已支持字段填充到表单。"""
        waveform = request.waveform
        scenario = request.scenario
        jammer = request.jammer
        settings = request.evaluation

        self.waveform_type_combo.setCurrentText(waveform.waveform_type)
        self.name_edit.setText(waveform.name)
        self.carrier_frequency_ghz.setValue(_hz_to_ghz(waveform.carrier_frequency_hz))
        self.bandwidth_mhz.setValue(_hz_to_mhz(waveform.bandwidth_hz))
        self.pulse_width_us.setValue(_s_to_us(waveform.pulse_width_s))
        self.sample_rate_mhz.setValue(_hz_to_mhz(waveform.sample_rate_hz))
        self.peak_power_w.setValue(waveform.peak_power_w)
        if waveform.phase_code is None:
            phase_code_text = ""
        else:
            phase_code_text = ",".join(str(value) for value in waveform.phase_code)
        self.phase_code_edit.setText(phase_code_text)

        self.target_range_km.setValue(scenario.target_range_m / 1000.0)
        self.target_velocity_mps.setValue(scenario.target_radial_velocity_mps)
        self.noise_variance.setValue(settings.noise_variance)
        self.pfa.setValue(settings.pfa)
        self.target_pd.setValue(settings.target_pd or 0.9)
        self.occupied_power_fraction.setValue(settings.occupied_power_fraction)
        self.num_pulses.setValue(settings.num_pulses or 64)
        self.prf_hz.setValue(settings.prf_hz or 1000.0)
        self.jammer_enabled.setChecked(jammer.enabled and jammer.jammer_type == "noise")
        self.jsr_db.setValue(jammer.jammer_to_signal_ratio_db)

    def build_request(self, base_request: EvaluationRequest | None) -> EvaluationRequest:
        """根据表单构造新的 EvaluationRequest，不计算任何雷达指标。"""
        request = base_request or EvaluationRequest()
        waveform = WaveformConfig(
            waveform_type=self.waveform_type_combo.currentText(),
            name=self.name_edit.text().strip() or "desktop_waveform",
            carrier_frequency_hz=_ghz_to_hz(self.carrier_frequency_ghz.value()),
            bandwidth_hz=_mhz_to_hz(self.bandwidth_mhz.value()),
            pulse_width_s=_us_to_s(self.pulse_width_us.value()),
            sample_rate_hz=_mhz_to_hz(self.sample_rate_mhz.value()),
            peak_power_w=self.peak_power_w.value(),
            phase_code=self._phase_code_for_current_waveform(),
        )
        scenario = ScenarioConfig(
            name=request.scenario.name,
            target_range_m=self.target_range_km.value() * 1000.0,
            target_radial_velocity_mps=self.target_velocity_mps.value(),
            signal_to_noise_ratio_db=request.scenario.signal_to_noise_ratio_db,
        )
        jammer = JammerConfig(
            enabled=self.jammer_enabled.isChecked(),
            jammer_type="noise" if self.jammer_enabled.isChecked() else "none",
            jammer_to_signal_ratio_db=self.jsr_db.value(),
        )
        evaluation = request.evaluation.model_copy(
            update={
                "noise_variance": self.noise_variance.value(),
                "pfa": self.pfa.value(),
                "target_pd": self.target_pd.value(),
                "occupied_power_fraction": self.occupied_power_fraction.value(),
                "num_pulses": self.num_pulses.value(),
                "prf_hz": self.prf_hz.value(),
            },
        )
        return EvaluationRequest(
            waveform=waveform,
            scenario=scenario,
            jammer=jammer,
            evaluation=EvaluationSettings.model_validate(evaluation),
        )

    def set_busy(self, busy: bool) -> None:
        """设置评估运行时的控件可用状态。"""
        self.start_button.setEnabled(not busy)

    def _build_controls(self) -> None:
        self.waveform_type_combo = QComboBox()
        self.waveform_type_combo.addItems(["rect", "lfm", "phase_code"])
        self.name_edit = QLineEdit()
        self.carrier_frequency_ghz = _double_spin(0.001, 1000.0, " GHz", 3, 10.0)
        self.bandwidth_mhz = _double_spin(0.001, 100000.0, " MHz", 3, 20.0)
        self.pulse_width_us = _double_spin(0.001, 1000000.0, " us", 3, 20.0)
        self.sample_rate_mhz = _double_spin(0.001, 100000.0, " MHz", 3, 100.0)
        self.peak_power_w = _double_spin(0.001, 1e9, " W", 3, 1.0)
        self.phase_code_edit = QLineEdit()
        self.phase_code_edit.setPlaceholderText("1,1,1,-1,-1,1,-1")

        self.target_range_km = _double_spin(0.001, 1e6, " km", 3, 50.0)
        self.target_velocity_mps = _double_spin(-100000.0, 100000.0, " m/s", 3, 100.0)
        self.noise_variance = _double_spin(1e-12, 1e12, "", 9, 1.0)
        self.pfa = _double_spin(1e-12, 0.999999, "", 12, 1e-6)
        self.target_pd = _double_spin(0.001, 0.999999, "", 6, 0.9)
        self.occupied_power_fraction = _double_spin(0.001, 0.999999, "", 6, 0.99)
        self.num_pulses = QSpinBox()
        self.num_pulses.setRange(1, 1000000)
        self.num_pulses.setValue(64)
        self.prf_hz = _double_spin(0.001, 1e9, " Hz", 3, 1000.0)
        self.jammer_enabled = QCheckBox("启用宽带噪声压制干扰")
        self.jsr_db = _double_spin(-120.0, 120.0, " dB", 3, 3.0)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(12, 12, 12, 12)
        scroll_layout.setSpacing(10)
        scroll_layout.addWidget(self._build_waveform_group())
        scroll_layout.addWidget(self._build_scenario_group())
        scroll_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(scroll_content)

        self.start_button = QPushButton("▶ 开始评估")
        self.start_button.setObjectName("RunButton")
        self.start_button.clicked.connect(self.start_requested.emit)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(scroll_area, stretch=1)
        root_layout.addWidget(self.start_button)

    def _build_waveform_group(self) -> QGroupBox:
        group = QGroupBox("波形定义")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("波形类型", self.waveform_type_combo)
        form.addRow("名称", self.name_edit)
        form.addRow("载频", self.carrier_frequency_ghz)
        form.addRow("带宽", self.bandwidth_mhz)
        form.addRow("脉宽", self.pulse_width_us)
        form.addRow("采样率", self.sample_rate_mhz)
        form.addRow("峰值功率", self.peak_power_w)
        form.addRow("相位码", self.phase_code_edit)
        return group

    def _build_scenario_group(self) -> QGroupBox:
        group = QGroupBox("场景与环境")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("目标距离", self.target_range_km)
        form.addRow("目标速度", self.target_velocity_mps)
        form.addRow("噪声方差", self.noise_variance)
        form.addRow("Pfa", self.pfa)
        form.addRow("目标 Pd", self.target_pd)
        form.addRow("占用功率比例", self.occupied_power_fraction)
        form.addRow("脉冲数", self.num_pulses)
        form.addRow("PRF", self.prf_hz)
        form.addRow("干扰开关", self.jammer_enabled)
        form.addRow("干信比", self.jsr_db)
        return group

    def _phase_code_for_current_waveform(self) -> list[int] | None:
        if self.waveform_type_combo.currentText() != "phase_code":
            return None
        text = self.phase_code_edit.text().strip()
        if not text:
            raise ValueError("phase_code 波形必须填写相位码序列。")
        try:
            return [int(part.strip()) for part in text.split(",") if part.strip()]
        except ValueError as exc:
            raise ValueError("相位码只能包含整数，并使用英文逗号分隔。") from exc


class ChartPanel(QFrame):
    """pyqtgraph 图表面板；依赖缺失时退化为文本占位。"""

    def __init__(self, title: str) -> None:
        """创建一个可绘制曲线或热力图的面板。"""
        super().__init__()
        self.setObjectName("ChartFrame")
        self._title = title
        self._plot_widget: Any | None = None
        self._fallback_label: QLabel | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("MetricCardTitle")
        layout.addWidget(title_label)

        if pg is None:
            self._fallback_label = QLabel("pyqtgraph 未安装，图表区域暂不可用")
            self._fallback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self._fallback_label, stretch=1)
        else:
            self._plot_widget = pg.PlotWidget(background="#0b1220")
            self._plot_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            self._plot_widget.showGrid(x=True, y=True, alpha=0.25)
            layout.addWidget(self._plot_widget, stretch=1)

    def show_message(self, message: str) -> None:
        """显示不可用提示。"""
        if self._plot_widget is not None:
            self._plot_widget.clear()
            self._plot_widget.setTitle(message, color="#94a3b8")
        if self._fallback_label is not None:
            self._fallback_label.setText(message)

    def plot_curve(
        self,
        x_values: list[float],
        y_values: list[float],
        *,
        x_label: str,
        y_label: str,
    ) -> None:
        """绘制来自 chart_data 的曲线，不重新计算指标。"""
        if self._plot_widget is None:
            self.show_message(f"{self._title} 数据已准备，当前环境未安装 pyqtgraph")
            return
        self._plot_widget.clear()
        self._plot_widget.setTitle("")
        self._plot_widget.setLabel("bottom", x_label)
        self._plot_widget.setLabel("left", y_label)
        self._plot_widget.plot(
            np.asarray(x_values, dtype=float),
            np.asarray(y_values, dtype=float),
            pen=pg.mkPen("#38bdf8", width=2),
        )

    def plot_heatmap(
        self,
        x_values: list[float],
        y_values: list[float],
        matrix: list[list[float]],
    ) -> None:
        """显示来自 chart_data 的模糊函数热力图。"""
        if self._plot_widget is None:
            self.show_message(f"{self._title} 数据已准备，当前环境未安装 pyqtgraph")
            return
        image = np.asarray(matrix, dtype=float)
        if image.ndim != 2 or image.size == 0:
            self.show_message("模糊函数图数据不可用")
            return
        self._plot_widget.clear()
        self._plot_widget.setTitle("")
        self._plot_widget.setLabel("bottom", "Delay samples")
        self._plot_widget.setLabel("left", "Doppler Hz")
        image_item = pg.ImageItem(image.T)
        self._plot_widget.addItem(image_item)
        if x_values and y_values:
            x_min = float(min(x_values))
            y_min = float(min(y_values))
            x_span = float(max(x_values) - x_min) or 1.0
            y_span = float(max(y_values) - y_min) or 1.0
            image_item.setRect(x_min, y_min, x_span, y_span)
        self._plot_widget.autoRange()


class MetricCard(QFrame):
    """看板顶部的关键指标卡片。"""

    def __init__(self, title: str, value: str = "-") -> None:
        """创建指标卡片。"""
        super().__init__()
        self.setObjectName("MetricCard")
        self._value_label = QLabel(value)
        self._value_label.setObjectName("MetricCardValue")
        title_label = QLabel(title)
        title_label.setObjectName("MetricCardTitle")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.addWidget(title_label)
        layout.addWidget(self._value_label)

    def set_value(self, value: str) -> None:
        """更新卡片值。"""
        self._value_label.setText(value)


class RightWorkspace(QWidget):
    """右侧主工作区。"""

    def __init__(self) -> None:
        """创建面包屑、预览 Tab 和评估看板 Tab。"""
        super().__init__()
        self.breadcrumb = QLabel("当前参数：-")
        self.breadcrumb.setObjectName("Breadcrumb")
        self.tabs = QTabWidget()
        self.preview_chart = ChartPanel("波形时域/频域预览区")
        self.ambiguity_chart = ChartPanel("模糊函数图渲染区")
        self.spectrum_chart = ChartPanel("频谱图渲染区")
        self.score_value = QLabel("--")
        self.score_value.setObjectName("ScoreValue")
        self.metric_cards = {
            "pd": MetricCard("检测概率 Pd"),
            "range_resolution": MetricCard("距离分辨率"),
            "jammed_pd": MetricCard("干扰下 Pd"),
            "occupied_bandwidth": MetricCard("占用带宽"),
        }
        self.metric_table = QTableWidget(0, 4)
        self.metric_table.setHorizontalHeaderLabels(["指标名称", "计算结果", "单位", "状态/备注"])
        self.metric_table.horizontalHeader().setStretchLastSection(True)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(12)
        root_layout.addWidget(self.breadcrumb)
        root_layout.addWidget(self.tabs, stretch=1)
        self.tabs.addTab(self._build_preview_tab(), "波形设计与预览")
        self.tabs.addTab(self._build_dashboard_tab(), "综合评估看板")
        self.show_demo_dashboard()

    def update_from_request(self, request: EvaluationRequest | None) -> None:
        """根据当前请求更新摘要文本。"""
        if request is None:
            self.breadcrumb.setText("当前参数：未加载配置")
            return
        waveform = request.waveform
        self.breadcrumb.setText(
            "当前参数："
            f"{waveform.waveform_type.upper()} | "
            f"{_hz_to_ghz(waveform.carrier_frequency_hz):.3g} GHz | "
            f"{_hz_to_mhz(waveform.bandwidth_hz):.3g} MHz",
        )

    def update_from_result(self, result: EvaluationResult) -> None:
        """使用 EvaluationResult 刷新看板，不重新计算指标。"""
        self.update_from_request(result.request)
        self.score_value.setText(f"{result.overall_score:.1f}")
        metrics = {metric.metric_id: metric for metric in result.raw_metrics}
        self.metric_cards["pd"].set_value(_metric_value_text(metrics.get("detection.pd")))
        self.metric_cards["range_resolution"].set_value(
            _metric_value_text(metrics.get("resolution.range_resolution_m")),
        )
        self.metric_cards["jammed_pd"].set_value(_metric_value_text(metrics.get("anti_jamming.jammed_pd")))
        self.metric_cards["occupied_bandwidth"].set_value(
            _metric_value_text(metrics.get("lpi.occupied_bandwidth_hz")),
        )
        self._fill_metric_table(result.raw_metrics[:24])
        self._update_charts(result.chart_data)
        self.tabs.setCurrentIndex(1)

    def show_demo_dashboard(self) -> None:
        """显示未评估时的演示表格和占位图。"""
        self.score_value.setText("--")
        for card in self.metric_cards.values():
            card.set_value("-")
        rows = [
            ("检测性能", "-", "", "等待评估"),
            ("距离分辨率", "-", "m", "等待评估"),
            ("抗干扰性能", "-", "", "未开启干扰"),
        ]
        self.metric_table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                self.metric_table.setItem(row, column, QTableWidgetItem(value))
        self.preview_chart.show_message("波形时域/频域预览区")
        self.ambiguity_chart.show_message("模糊函数图渲染区")
        self.spectrum_chart.show_message("频谱图渲染区")

    def _build_preview_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        layout.addWidget(self.preview_chart, stretch=3)

        assumptions = QTextEdit()
        assumptions.setReadOnly(True)
        assumptions.setText(
            "当前环境模型假设：\n"
            "1. 指标计算全部由 radar_eval_core 完成。\n"
            "2. 探测性能采用已定义的匹配滤波平方律检测模型。\n"
            "3. 抗干扰仅对应宽带复高斯噪声压制干扰模型。\n"
            "4. 反侦察 / 低截获模块仅展示波形暴露特征，不计算截获概率。\n"
            "5. 图表区域仅展示 EvaluationResult.chart_data，不重新计算指标。",
        )
        layout.addWidget(assumptions, stretch=1)
        return tab

    def _build_dashboard_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        top_row = QHBoxLayout()
        score_card = QFrame()
        score_card.setObjectName("MetricCard")
        score_layout = QVBoxLayout(score_card)
        score_layout.addWidget(QLabel("综合评分"))
        score_layout.addWidget(self.score_value)
        top_row.addWidget(score_card, stretch=1)
        for card in self.metric_cards.values():
            top_row.addWidget(card, stretch=1)
        layout.addLayout(top_row)

        chart_row = QHBoxLayout()
        chart_row.addWidget(self.ambiguity_chart, stretch=1)
        chart_row.addWidget(self.spectrum_chart, stretch=1)
        layout.addLayout(chart_row, stretch=2)
        layout.addWidget(self.metric_table, stretch=2)
        return tab

    def _fill_metric_table(self, metrics: list[RawMetric]) -> None:
        self.metric_table.setRowCount(len(metrics))
        for row, metric in enumerate(metrics):
            value = "-" if metric.value is None else f"{metric.value:.8g}"
            remark = "可用" if metric.available else metric.reason or "不可用"
            values = [metric.description or metric.metric_id, value, metric.unit, remark]
            for column, item_value in enumerate(values):
                self.metric_table.setItem(row, column, QTableWidgetItem(item_value))

    def _update_charts(self, chart_data: dict[str, Any]) -> None:
        waveform = chart_data.get("waveform_preview")
        if isinstance(waveform, dict):
            self.preview_chart.plot_curve(
                waveform.get("time_s", []),
                waveform.get("magnitude", []),
                x_label="Time s",
                y_label="Magnitude",
            )
        else:
            self.preview_chart.show_message("波形预览数据不可用")

        heatmap = chart_data.get("ambiguity_heatmap")
        if isinstance(heatmap, dict):
            self.ambiguity_chart.plot_heatmap(
                heatmap.get("delay_samples", []),
                heatmap.get("doppler_hz", []),
                heatmap.get("magnitude_normalized", []),
            )
        else:
            self.ambiguity_chart.show_message("模糊函数图数据不可用")

        spectrum = chart_data.get("spectrum_psd")
        if isinstance(spectrum, dict):
            self.spectrum_chart.plot_curve(
                spectrum.get("frequency_hz", []),
                spectrum.get("psd_w_per_hz", []),
                x_label="Frequency Hz",
                y_label="PSD W/Hz",
            )
        else:
            self.spectrum_chart.show_message("频谱图数据不可用")


class MainWindow(QMainWindow):
    """雷达波形性能评估软件 V1.0 主窗口。"""

    def __init__(self, state: AppState | None = None) -> None:
        """初始化主窗口、参数面板、看板和后台评估连接。"""
        super().__init__()
        self._state = state or AppState(current_request=EvaluationRequest())
        self._evaluation_service = EvaluationService()
        self._project_service = ProjectService()
        self._thread: QThread | None = None
        self._worker: EvaluationWorker | None = None

        self.top_bar = TopBar()
        self.left_panel = LeftParameterPanel()
        self.workspace = RightWorkspace()
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.project_label = QLabel("项目：未保存")
        self.status_label = QLabel("就绪")

        self.setWindowTitle("雷达波形性能评估软件 V1.0")
        self.setMinimumSize(1180, 760)
        self.resize(1360, 860)
        self.setStyleSheet(SHELL_QSS)
        self._build_shell()
        self._build_menu()
        self._build_status_bar()
        self._connect_signals()
        self.refresh_all_pages()

    def refresh_all_pages(self) -> None:
        """刷新主窗口中所有与 AppState 相关的显示。"""
        self.left_panel.load_from_request(self._state.current_request or EvaluationRequest())
        self.workspace.update_from_request(self._state.current_request)
        if self._state.current_result is not None:
            self.workspace.update_from_result(self._state.current_result)
        self._update_project_label()

    def closeEvent(self, event: QCloseEvent) -> None:
        """退出前检查是否需要保存项目。"""
        if self._confirm_discard_or_save():
            event.accept()
        else:
            event.ignore()

    def _build_shell(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.workspace)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setSizes([360, 1000])
        root_layout.addWidget(self.top_bar)
        root_layout.addWidget(self.splitter, stretch=1)
        self.setCentralWidget(root)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        file_menu.addAction(_action(self, "加载默认 LFM 配置", self._load_default_lfm))
        file_menu.addAction(_action(self, "加载默认相位编码配置", self._load_default_phase_code))
        file_menu.addSeparator()
        file_menu.addAction(_action(self, "打开项目", self._open_project))
        file_menu.addAction(_action(self, "保存项目", self._save_project))
        file_menu.addSeparator()
        file_menu.addAction(_action(self, "导出完整评估 JSON", self._export_evaluation_json))
        file_menu.addAction(_action(self, "导出报告 Markdown", self._export_report_markdown))
        file_menu.addAction(_action(self, "导出报告 HTML", self._export_report_html))
        file_menu.addSeparator()
        file_menu.addAction(_action(self, "退出", self.close))

        evaluation_menu = self.menuBar().addMenu("评估")
        evaluation_menu.addAction(_action(self, "开始评估", self._start_evaluation))

        help_menu = self.menuBar().addMenu("帮助")
        help_menu.addAction(_action(self, "关于", self._show_about))

    def _build_status_bar(self) -> None:
        self.statusBar().addPermanentWidget(self.project_label, stretch=1)
        self.statusBar().addPermanentWidget(self.status_label)

    def _connect_signals(self) -> None:
        self.top_bar.load_default_button.clicked.connect(self._load_default_lfm)
        self.top_bar.export_report_button.clicked.connect(self._export_report_markdown)
        self.left_panel.start_requested.connect(self._start_evaluation)

    def _load_default_lfm(self) -> None:
        self._load_request_file(DEFAULT_REQUEST_PATH, "已加载默认 LFM 配置")

    def _load_default_phase_code(self) -> None:
        self._load_request_file(DEFAULT_PHASE_CODE_PATH, "已加载默认相位编码配置")

    def _load_request_file(self, path: Path, status_text: str) -> None:
        try:
            self._state.current_request = self._evaluation_service.load_request(path)
            self._state.current_scoring_config = self._evaluation_service.load_scoring_config(
                DEFAULT_SCORING_PATH,
            )
        except EvaluationServiceError as exc:
            QMessageBox.critical(self, "配置加载失败", str(exc))
            return
        self._state.current_result = None
        self._state.dirty = True
        self.workspace.show_demo_dashboard()
        self.refresh_all_pages()
        self._set_status(status_text)

    def _start_evaluation(self) -> None:
        if self._thread is not None:
            return
        try:
            request = self.left_panel.build_request(self._state.current_request)
            scoring_config = self._state.current_scoring_config or self._load_default_scoring()
        except Exception as exc:
            QMessageBox.critical(self, "参数校验失败", str(exc))
            return

        self._state.current_request = request
        self._state.current_scoring_config = scoring_config
        self._state.dirty = True
        self.workspace.update_from_request(request)

        self._thread = QThread(self)
        self._worker = EvaluationWorker(request, scoring_config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.started.connect(lambda: self._set_busy(True))
        self._worker.finished.connect(self._on_evaluation_finished)
        self._worker.failed.connect(self._on_evaluation_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.failed.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _load_default_scoring(self) -> ScoringConfig:
        return self._evaluation_service.load_scoring_config(DEFAULT_SCORING_PATH)

    def _on_evaluation_finished(self, result: object) -> None:
        if not isinstance(result, EvaluationResult):
            self._on_evaluation_failed("评估服务返回了无法识别的结果对象。")
            return
        self._state.current_result = result
        self._state.dirty = True
        self.workspace.update_from_result(result)
        self._set_status("评估完成")

    def _on_evaluation_failed(self, message: str) -> None:
        QMessageBox.critical(self, "评估失败", message)
        self._set_status("评估失败")

    def _on_thread_finished(self) -> None:
        self._set_busy(False)
        self._thread = None
        self._worker = None

    def _set_busy(self, busy: bool) -> None:
        self.left_panel.set_busy(busy)
        self.top_bar.load_default_button.setEnabled(not busy)
        self.top_bar.export_report_button.setEnabled(not busy)
        self._set_status("正在评估" if busy else "就绪")

    def _open_project(self) -> None:
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
        self._state.dirty = False
        self.refresh_all_pages()
        self._set_status("项目已打开")

    def _save_project(self) -> bool:
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
        self._update_project_label()
        self._set_status("项目已保存")
        return True

    def _export_evaluation_json(self) -> None:
        result = self._require_result()
        if result is None:
            return
        path_text, _ = QFileDialog.getSaveFileName(
            self,
            "导出完整评估 JSON",
            "evaluation_result.json",
            "JSON Files (*.json)",
        )
        if not path_text:
            return
        try:
            export_evaluation_json(result, Path(path_text))
        except ExportServiceError as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        self._set_status(f"已导出 {path_text}")

    def _export_report_markdown(self) -> None:
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
        )
        try:
            export_report_markdown(render_report_markdown(report), Path(path_text))
        except ExportServiceError as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        self._set_status(f"已导出 {path_text}")

    def _export_report_html(self) -> None:
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
        )
        try:
            export_report_html(render_report_html(report), Path(path_text))
        except ExportServiceError as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        self._set_status(f"已导出 {path_text}")

    def _require_result(self) -> EvaluationResult | None:
        if self._state.current_result is None:
            QMessageBox.information(self, "没有评估结果", "请先运行评估。")
            return None
        return self._state.current_result

    def _confirm_discard_or_save(self) -> bool:
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

    def _update_project_label(self) -> None:
        if self._state.current_project_path is None:
            self.project_label.setText("项目：未保存")
        else:
            self.project_label.setText(f"项目：{self._state.current_project_path}")

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)
        self.top_bar.set_status(text)

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "关于",
            "\n".join(
                [
                    f"{APP_NAME} {APP_VERSION}",
                    APP_STAGE,
                    "",
                    "技术栈：Python 3.12、PySide6 / QtWidgets、pyqtgraph、NumPy、SciPy、Pydantic。",
                    "当前功能：参数配置、后台评估、结构化结果展示、本地报告与 "
                    "JSON/Markdown/HTML 导出。",
                    "当前限制：不包含外部 API、数据库、截获概率、CFAR、Swerling 或复杂干扰模型。",
                ],
            ),
        )


def _action(parent: QMainWindow, text: str, slot: Callable[[], Any]) -> QAction:
    """创建菜单 QAction。"""
    action = QAction(text, parent)
    action.triggered.connect(lambda _checked=False: slot())
    return action


def _double_spin(
    minimum: float,
    maximum: float,
    suffix: str,
    decimals: int,
    value: float,
) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(decimals)
    spin.setValue(value)
    spin.setSuffix(suffix)
    spin.setKeyboardTracking(False)
    return spin


def _metric_value_text(metric: RawMetric | None) -> str:
    if metric is None or not metric.available or metric.value is None:
        return "-"
    if metric.unit:
        return f"{metric.value:.4g} {metric.unit}"
    return f"{metric.value:.4g}"


def _hz_to_ghz(value: float) -> float:
    return value / 1e9


def _ghz_to_hz(value: float) -> float:
    return value * 1e9


def _hz_to_mhz(value: float) -> float:
    return value / 1e6


def _mhz_to_hz(value: float) -> float:
    return value * 1e6


def _s_to_us(value: float) -> float:
    return value * 1e6


def _us_to_s(value: float) -> float:
    return value / 1e6


def _json_preview(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
