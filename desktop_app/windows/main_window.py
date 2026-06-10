"""雷达波形性能评估软件主界面。"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import numpy as np
from PySide6.QtCore import QPointF, Qt, QThread, Signal
from PySide6.QtGui import QAction, QCloseEvent, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
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
    WaveformType,
    derive_nominal_bandwidth_hz,
)
from radar_eval_core.scoring import ScoringConfig

try:
    import pyqtgraph as pg  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - 依赖同步前允许导入主窗口
    pg = None

try:
    import pyqtgraph.opengl as gl  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - OpenGL may be unavailable in headless environments.
    gl = None


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
QFrame#MetricCard, QFrame#PreviewTextFrame, QFrame#MacroPanel {
    background: #111827;
    border: 1px solid #2f3f55;
    border-radius: 8px;
}
QFrame#ChartFrame {
    background: #0b1220;
    border: none;
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
    font-size: 22px;
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
        self._update_waveform_parameter_visibility()

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
        self.waveform_type_combo.setObjectName("WaveformTypeCombo")
        self.waveform_type_combo.addItems(["rect", "lfm", "phase_code"])
        self.name_edit = QLineEdit()
        self.carrier_frequency_ghz = _double_spin(0.001, 1000.0, " GHz", 3, 10.0)
        self.bandwidth_mhz = _double_spin(0.001, 100000.0, " MHz", 3, 20.0)
        self.bandwidth_mhz.setObjectName("EditableBandwidthMHz")
        self.derived_bandwidth_label = QLabel("")
        self.derived_bandwidth_label.setObjectName("DerivedBandwidthLabel")
        self.derived_bandwidth_label.setStyleSheet("color: #cbd5e1; padding-left: 4px;")
        self.pulse_width_us = _double_spin(0.001, 1000000.0, " us", 3, 20.0)
        self.sample_rate_mhz = _double_spin(0.001, 100000.0, " MHz", 3, 100.0)
        self.peak_power_w = _double_spin(0.001, 1e9, " W", 3, 1.0)
        self.phase_code_edit = QLineEdit()
        self.phase_code_edit.setObjectName("PhaseCodeEdit")
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

        self._waveform_row_labels: dict[QWidget, QLabel] = {}
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

        self.waveform_type_combo.currentTextChanged.connect(
            lambda _text: self._update_waveform_parameter_visibility(),
        )
        self.pulse_width_us.valueChanged.connect(
            lambda _value: self._refresh_derived_bandwidth_label(),
        )
        self.phase_code_edit.textChanged.connect(
            lambda _text: self._refresh_derived_bandwidth_label(),
        )
        self._update_waveform_parameter_visibility()

    def _build_waveform_group(self) -> QGroupBox:
        group = QGroupBox("波形定义")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._add_waveform_row(form, "波形类型", self.waveform_type_combo)
        self._add_waveform_row(form, "名称", self.name_edit)
        self._add_waveform_row(form, "载频", self.carrier_frequency_ghz)
        self._add_waveform_row(form, "带宽", self.bandwidth_mhz)
        self._add_waveform_row(form, "带宽", self.derived_bandwidth_label)
        self._add_waveform_row(form, "脉宽", self.pulse_width_us)
        self._add_waveform_row(form, "采样率", self.sample_rate_mhz)
        self._add_waveform_row(form, "峰值功率", self.peak_power_w)
        self._add_waveform_row(form, "相位码", self.phase_code_edit)
        return group

    def _add_waveform_row(self, form: QFormLayout, label_text: str, field: QWidget) -> None:
        """添加波形表单行，并记录标签便于按波形类型隐藏。"""
        form.addRow(label_text, field)
        label = form.labelForField(field)
        if isinstance(label, QLabel):
            self._waveform_row_labels[field] = label

    def _set_waveform_row_visible(self, field: QWidget, visible: bool) -> None:
        field.setVisible(visible)
        label = self._waveform_row_labels.get(field)
        if label is not None:
            label.setVisible(visible)

    def _update_waveform_parameter_visibility(self) -> None:
        waveform_type = self.waveform_type_combo.currentText()
        self._set_waveform_row_visible(self.bandwidth_mhz, waveform_type == "lfm")
        self._set_waveform_row_visible(
            self.derived_bandwidth_label,
            waveform_type in {"rect", "phase_code"},
        )
        self._set_waveform_row_visible(self.phase_code_edit, waveform_type == "phase_code")
        self._refresh_derived_bandwidth_label()

    def _refresh_derived_bandwidth_label(self) -> None:
        waveform_type = self.waveform_type_combo.currentText()
        if waveform_type == "lfm":
            self.derived_bandwidth_label.setText("")
            return

        phase_code: list[int] | None = None
        if waveform_type == "phase_code":
            try:
                phase_code = self._parse_phase_code_text()
            except ValueError:
                self.derived_bandwidth_label.setText("待填写有效相位码")
                return

        try:
            waveform_type_value = cast(WaveformType, waveform_type)
            bandwidth_hz = derive_nominal_bandwidth_hz(
                waveform_type_value,
                _us_to_s(self.pulse_width_us.value()),
                phase_code=phase_code,
                explicit_bandwidth_hz=_mhz_to_hz(self.bandwidth_mhz.value()),
            )
        except ValueError:
            self.derived_bandwidth_label.setText("无法计算")
            return

        self.derived_bandwidth_label.setText(_frequency_text_from_hz(bandwidth_hz))

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
        return self._parse_phase_code_text()

    def _parse_phase_code_text(self) -> list[int]:
        text = self.phase_code_edit.text().strip()
        if not text:
            raise ValueError("phase_code 波形必须填写相位码序列。")
        try:
            phase_code = [int(part.strip()) for part in text.split(",") if part.strip()]
        except ValueError as exc:
            raise ValueError("相位码只能包含整数，并使用英文逗号分隔。") from exc
        if not phase_code:
            raise ValueError("phase_code 波形必须填写相位码序列。")
        return phase_code


class ChartPanel(QFrame):
    """pyqtgraph 图表面板；依赖缺失时退化为文本占位。"""

    def __init__(self, title: str) -> None:
        """创建一个可绘制曲线或热力图的面板。"""
        super().__init__()
        self.setObjectName("ChartFrame")
        self._title = title
        self._plot_widget: Any | None = None
        self._gl_widget: Any | None = None
        self._fallback_label: QLabel | None = None
        self._caption_label = QLabel("")
        self._caption_label.setStyleSheet("color: #94a3b8; padding: 3px 6px;")
        self._caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._caption_label.hide()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        if pg is None:
            self._fallback_label = QLabel("pyqtgraph 未安装，图表区域暂不可用")
            self._fallback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(self._fallback_label, stretch=1)
        else:
            self._plot_widget = pg.PlotWidget(background="#0b1220")
            self._plot_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            self._plot_widget.showGrid(x=True, y=True, alpha=0.25)
            self._layout.addWidget(self._plot_widget, stretch=1)
        self._layout.addWidget(self._caption_label)

    def show_message(self, message: str) -> None:
        """显示不可用提示。"""
        if self._gl_widget is not None:
            self._gl_widget.hide()
        if self._plot_widget is not None:
            self._plot_widget.show()
            self._plot_widget.clear()
            self._plot_widget.setTitle(message, color="#94a3b8")
        if self._fallback_label is not None:
            self._fallback_label.setText(message)
        self._caption_label.hide()

    def plot_curve(
        self,
        x_values: list[float],
        y_values: list[float],
        *,
        x_label: str,
        y_label: str,
        x_range: tuple[float, float] | None = None,
        y_range: tuple[float, float] | None = None,
    ) -> None:
        """绘制来自 chart_data 的曲线，不重新计算指标。"""
        if self._plot_widget is None:
            self.show_message(f"{self._title} 数据已准备，当前环境未安装 pyqtgraph")
            return
        if self._gl_widget is not None:
            self._gl_widget.hide()
        self._plot_widget.show()
        self._caption_label.hide()
        self._plot_widget.clear()
        self._plot_widget.setTitle("")
        self._plot_widget.setLabel("bottom", x_label)
        self._plot_widget.setLabel("left", y_label)
        self._plot_widget.plot(
            np.asarray(x_values, dtype=float),
            np.asarray(y_values, dtype=float),
            pen=pg.mkPen("#38bdf8", width=2),
        )
        if x_range is not None:
            self._plot_widget.setXRange(x_range[0], x_range[1], padding=0)
        if y_range is not None:
            self._plot_widget.setYRange(y_range[0], y_range[1], padding=0)

    def plot_ambiguity_surface(
        self,
        x_values: list[float],
        y_values: list[float],
        matrix: list[list[float]],
        *,
        x_label: str = "Delay samples",
    ) -> None:
        """Render normalized ambiguity magnitude as a -60..0 dB 3D surface."""
        if pg is None or gl is None:
            self.show_message("当前环境不支持 pyqtgraph OpenGL 3D 模糊函数图")
            return

        x_axis = np.asarray(x_values, dtype=float)
        y_axis_hz = np.asarray(y_values, dtype=float)
        image = np.asarray(matrix, dtype=float)
        if (
            x_axis.ndim != 1
            or y_axis_hz.ndim != 1
            or x_axis.size == 0
            or y_axis_hz.size == 0
            or image.ndim != 2
            or image.shape != (y_axis_hz.size, x_axis.size)
        ):
            self.show_message("模糊函数 3D 图数据不可用")
            return

        try:
            image_db = _ambiguity_db_image(image)
        except ValueError:
            self.show_message("ambiguity surface peak is unavailable")
            return

        try:
            gl_widget = self._ensure_gl_widget()
        except Exception:
            self.show_message("当前 OpenGL 环境无法创建 3D 模糊函数图")
            return

        if self._plot_widget is not None:
            self._plot_widget.hide()
        gl_widget.show()
        self._clear_gl_items(gl_widget)

        y_axis, y_label = _scaled_doppler_axis(y_axis_hz)
        x_display = _normalized_surface_axis(x_axis)
        y_display = _normalized_surface_axis(y_axis)
        z_surface_db = image_db.T.astype(float, copy=False)
        z_display = (z_surface_db + 60.0) / 60.0
        surface = gl.GLSurfacePlotItem(
            x=x_display,
            y=y_display,
            z=z_display,
            colors=_ambiguity_surface_colors(z_surface_db),
            shader=None,
            smooth=False,
        )
        surface.setGLOptions("opaque")
        gl_widget.addItem(surface)

        grid = gl.GLGridItem()
        grid.setSize(2.0, 2.0, 1.0)
        grid.setSpacing(0.5, 0.5, 1.0)
        grid.translate(0.0, 0.0, 0.0)
        gl_widget.addItem(grid)

        axis = gl.GLAxisItem()
        axis.setSize(1.0, 1.0, 1.0)
        axis.translate(-1.0, -1.0, 0.0)
        gl_widget.addItem(axis)

        gl_widget.setCameraPosition(distance=4.0, elevation=34, azimuth=-45)
        self._caption_label.setText(
            "3D ambiguity surface: "
            f"{x_label} [{_compact_number(float(np.min(x_axis)))}, "
            f"{_compact_number(float(np.max(x_axis)))}], "
            f"{y_label} [{_compact_number(float(np.min(y_axis)))}, "
            f"{_compact_number(float(np.max(y_axis)))}], Z -60..0 dB",
        )
        self._caption_label.show()

    def _ensure_gl_widget(self) -> Any:
        if self._gl_widget is None:
            self._gl_widget = gl.GLViewWidget()
            self._gl_widget.setBackgroundColor("#0b1220")
            self._gl_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            self._layout.insertWidget(0, self._gl_widget, stretch=1)
        return self._gl_widget

    @staticmethod
    def _clear_gl_items(gl_widget: Any) -> None:
        for item in list(getattr(gl_widget, "items", [])):
            gl_widget.removeItem(item)


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
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(6)
        layout.addWidget(title_label)
        layout.addStretch(1)
        layout.addWidget(self._value_label, alignment=Qt.AlignmentFlag.AlignBottom)

    def set_value(self, value: str) -> None:
        """更新卡片值。"""
        self._value_label.setText(value)


class RadarChartWidget(QWidget):
    """六维评分雷达图控件，只展示 EvaluationResult 中已有轴得分。"""

    axis_order = [
        "detection",
        "resolution",
        "sidelobe_ambiguity",
        "anti_jamming",
        "lpi",
        "engineering",
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化雷达图维度、默认值和暗色主题配色。"""
        super().__init__(parent)
        self.setMinimumSize(260, 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.dimensions = [
            "探测性能",
            "分辨能力",
            "旁瓣与模糊控制",
            "抗干扰性能",
            "低截获暴露特征",
            "工程可实现性",
        ]
        self.values = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.grid_color = QColor(148, 163, 184, 120)
        self.axis_color = QColor(148, 163, 184, 150)
        self.data_line_color = QColor(56, 189, 248)
        self.data_fill_color = QColor(56, 189, 248, 70)
        self.text_color = QColor(226, 232, 240)
        self.setToolTip("等待评估结果")

    def update_data(self, new_values: list[float]) -> None:
        """使用 6 个百分制轴得分刷新雷达图。"""
        if len(new_values) != 6:
            return
        self.values = [float(max(0.0, min(value, 100.0))) for value in new_values]
        self.update()

    def update_from_axis_scores(self, axis_scores: list[Any]) -> None:
        """从 EvaluationResult.axis_scores 刷新雷达图，不计算新指标。"""
        axis_by_id = {getattr(axis, "axis_id", ""): axis for axis in axis_scores}
        values: list[float] = []
        tooltip_lines = ["六维评分："]
        for axis_id, display_name in zip(self.axis_order, self.dimensions, strict=True):
            axis = axis_by_id.get(axis_id)
            score = getattr(axis, "score", None)
            available = bool(getattr(axis, "available", False))
            if axis is not None and available and score is not None:
                value = float(score)
                tooltip_lines.append(f"{display_name}: {value:.2f}")
            else:
                value = 0.0
                reason = getattr(axis, "reason", None) if axis is not None else "结果中缺少该维度"
                tooltip_lines.append(f"{display_name}: 不可用（{reason or '未说明原因'}）")
            values.append(value)
        self.update_data(values)
        self.setToolTip("\n".join(tooltip_lines))

    def paintEvent(self, event: object) -> None:
        """绘制六边形网格、维度轴和评分填充区域。"""
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()
        center = QPointF(width / 2, height / 2)
        radius = min(width, height) / 2 * 0.52
        num_dim = len(self.dimensions)
        angle_step = 2 * math.pi / num_dim

        painter.setPen(QPen(self.grid_color, 1, Qt.PenStyle.DashLine))
        for i in range(1, 6):
            r = radius * (i / 5.0)
            poly = QPolygonF()
            for j in range(num_dim):
                angle = j * angle_step - math.pi / 2
                poly.append(
                    QPointF(
                        center.x() + r * math.cos(angle),
                        center.y() + r * math.sin(angle),
                    ),
                )
            painter.drawPolygon(poly)

        font = QFont("Microsoft YaHei UI", 9, QFont.Weight.Bold)
        painter.setFont(font)
        for j in range(num_dim):
            angle = j * angle_step - math.pi / 2
            end_point = QPointF(
                center.x() + radius * math.cos(angle),
                center.y() + radius * math.sin(angle),
            )
            painter.setPen(QPen(self.axis_color, 1, Qt.PenStyle.SolidLine))
            painter.drawLine(center, end_point)

            text_radius = radius * 1.2
            text_x = center.x() + text_radius * math.cos(angle)
            text_y = center.y() + text_radius * math.sin(angle)
            painter.setPen(QPen(self.text_color))
            painter.drawText(int(text_x - 46), int(text_y + 5), self.dimensions[j])

        data_poly = QPolygonF()
        for j, value in enumerate(self.values):
            angle = j * angle_step - math.pi / 2
            val_radius = radius * (value / 100.0)
            data_poly.append(
                QPointF(
                    center.x() + val_radius * math.cos(angle),
                    center.y() + val_radius * math.sin(angle),
                ),
            )

        painter.setPen(QPen(self.data_line_color, 2, Qt.PenStyle.SolidLine))
        painter.setBrush(self.data_fill_color)
        painter.drawPolygon(data_poly)


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
        self.radar_chart = RadarChartWidget()
        self.metric_cards = {
            "pd": MetricCard("检测概率 Pd"),
            "range_resolution": MetricCard("距离分辨率"),
            "jammed_pd": MetricCard("干扰下 Pd"),
            "occupied_bandwidth": MetricCard("占用带宽"),
        }
        self.metric_table = QTableWidget(0, 4)
        self.metric_table.setHorizontalHeaderLabels(["指标名称", "计算结果", "单位", "状态/备注"])
        header = self.metric_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

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
        self.radar_chart.update_from_axis_scores(result.axis_scores)
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
        self.radar_chart.update_data([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.radar_chart.setToolTip("等待评估结果")
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

        macro_panel = QFrame()
        macro_panel.setObjectName("MacroPanel")
        macro_panel.setMaximumHeight(320)
        macro_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        top_row = QHBoxLayout(macro_panel)
        top_row.setContentsMargins(12, 12, 12, 12)
        top_row.setSpacing(12)
        score_card = QFrame()
        score_card.setObjectName("MetricCard")
        score_card.setMinimumWidth(150)
        score_card.setMaximumWidth(190)
        score_layout = QVBoxLayout(score_card)
        score_layout.setContentsMargins(14, 14, 14, 14)
        score_layout.addWidget(QLabel("综合评分"))
        score_layout.addStretch(1)
        score_layout.addWidget(self.score_value)

        summary_panel = QWidget()
        summary_grid = QGridLayout(summary_panel)
        summary_grid.setContentsMargins(0, 0, 0, 0)
        summary_grid.setSpacing(12)
        summary_grid.addWidget(self.metric_cards["pd"], 0, 0)
        summary_grid.addWidget(self.metric_cards["range_resolution"], 0, 1)
        summary_grid.addWidget(self.metric_cards["jammed_pd"], 1, 0)
        summary_grid.addWidget(self.metric_cards["occupied_bandwidth"], 1, 1)
        summary_grid.setRowStretch(0, 1)
        summary_grid.setRowStretch(1, 1)
        summary_grid.setColumnStretch(0, 1)
        summary_grid.setColumnStretch(1, 1)

        top_row.addWidget(score_card)
        top_row.addWidget(self.radar_chart, stretch=1)
        top_row.addWidget(summary_panel, stretch=1)
        layout.addWidget(macro_panel, stretch=0)

        chart_row = QHBoxLayout()
        chart_row.addWidget(self.ambiguity_chart, stretch=1)
        chart_row.addWidget(self.spectrum_chart, stretch=1)
        layout.addLayout(chart_row, stretch=3)
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
            y_values = waveform.get("real_amplitude", waveform.get("magnitude", []))
            preview_duration_s = waveform.get("preview_duration_s")
            x_range = (
                (0.0, float(preview_duration_s))
                if isinstance(preview_duration_s, int | float)
                else None
            )
            self.preview_chart.plot_curve(
                waveform.get("time_s", []),
                y_values,
                x_label="Time s",
                y_label="Amplitude (Real Part)",
                x_range=x_range,
                y_range=(-1.5, 1.5),
            )
        else:
            self.preview_chart.show_message("波形预览数据不可用")

        heatmap = chart_data.get("ambiguity_heatmap")
        if isinstance(heatmap, dict):
            x_values = heatmap.get("delay_us")
            x_label = "Delay us"
            if not x_values:
                x_values = heatmap.get("delay_samples", [])
                x_label = "Delay samples"
            self.ambiguity_chart.plot_ambiguity_surface(
                x_values,
                heatmap.get("doppler_hz", []),
                heatmap.get("magnitude_normalized", []),
                x_label=x_label,
            )
        else:
            self.ambiguity_chart.show_message("模糊函数图数据不可用")

        spectrum = chart_data.get("spectrum_psd")
        if isinstance(spectrum, dict):
            frequency_values = spectrum.get("frequency_mhz")
            frequency_label = "Frequency MHz"
            if not frequency_values:
                frequency_values = spectrum.get("frequency_hz", [])
                frequency_label = "Frequency Hz"
            psd_values = spectrum.get("psd_relative_db")
            psd_label = "Relative PSD dB"
            if not psd_values:
                psd_values = spectrum.get("psd_w_per_hz", [])
                psd_label = "PSD W/Hz"
            self.spectrum_chart.plot_curve(
                frequency_values,
                psd_values,
                x_label=frequency_label,
                y_label=psd_label,
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
    value, unit = _display_value_and_unit(metric.value, metric.unit)
    if unit:
        return f"{_compact_number(value)} {unit}"
    return _compact_number(value)


def _frequency_text_from_hz(value_hz: float) -> str:
    value, unit = _display_value_and_unit(value_hz, "Hz")
    return f"{_compact_number(value)} {unit}"


def _display_value_and_unit(value: float, unit: str) -> tuple[float, str]:
    abs_value = abs(value)
    if unit == "Hz" and abs_value >= 1e6:
        return value / 1e6, "MHz"
    if unit == "Hz" and abs_value >= 1e3:
        return value / 1e3, "kHz"
    return value, unit


def _ambiguity_db_image(image: np.ndarray) -> np.ndarray:
    """将归一化线性幅度矩阵转换为用于显示的 -60 到 0 dB 矩阵。"""
    peak = float(np.max(image))
    if not math.isfinite(peak) or peak <= 0.0:
        raise ValueError("ambiguity heatmap peak must be positive.")
    safe_image = np.maximum(image, np.finfo(float).tiny)
    image_db = 20.0 * np.log10(safe_image / peak)
    return np.clip(image_db, -60.0, 0.0)


def _ambiguity_colormap_lut() -> np.ndarray:
    """返回模糊函数 dB 热力图使用的伪彩色查找表。"""
    if pg is not None:
        try:
            return pg.colormap.get("viridis").getLookupTable(nPts=256)
        except Exception:
            colors = np.array(
                [
                    [0, 0, 128],
                    [0, 128, 255],
                    [0, 220, 120],
                    [255, 230, 0],
                    [255, 0, 0],
                ],
                dtype=np.ubyte,
            )
            positions = np.linspace(0.0, 1.0, colors.shape[0])
            return pg.ColorMap(positions, colors).getLookupTable(nPts=256)
    return np.empty((0, 4), dtype=np.ubyte)


def _ambiguity_surface_colors(image_db: np.ndarray) -> np.ndarray:
    """Map a -60..0 dB ambiguity surface to flattened OpenGL vertex colors."""
    lut = _ambiguity_colormap_lut()
    if lut.size == 0:
        return np.ones((*image_db.shape, 4), dtype=float)
    if lut.shape[1] == 3:
        alpha = np.full((lut.shape[0], 1), 255, dtype=lut.dtype)
        lut = np.hstack([lut, alpha])
    color_index = np.clip(((image_db + 60.0) / 60.0 * 255.0).astype(int), 0, 255)
    return (lut[color_index].astype(float) / 255.0).reshape(-1, 4)


def _scaled_doppler_axis(doppler_hz: np.ndarray) -> tuple[np.ndarray, str]:
    """Return a display-scaled Doppler axis while preserving chart_data values."""
    max_abs = float(np.max(np.abs(doppler_hz))) if doppler_hz.size else 0.0
    if max_abs >= 1e6:
        return doppler_hz / 1e6, "Doppler MHz"
    if max_abs >= 1e3:
        return doppler_hz / 1e3, "Doppler kHz"
    return doppler_hz, "Doppler Hz"


def _normalized_surface_axis(values: np.ndarray) -> np.ndarray:
    """Normalize a physical axis to [-1, 1] for readable 3D OpenGL display."""
    if values.size == 0:
        return values.astype(float, copy=True)
    span = float(np.ptp(values))
    if span <= 0.0:
        return np.zeros_like(values, dtype=float)
    center = float(np.min(values) + span / 2.0)
    return (values.astype(float, copy=False) - center) / (span / 2.0)


def _compact_number(value: float) -> str:
    if not math.isfinite(value):
        return str(value)
    abs_value = abs(value)
    if abs_value == 0:
        return "0"
    if abs_value >= 1000:
        return f"{value:,.3f}".rstrip("0").rstrip(".")
    if abs_value >= 1:
        return f"{value:.3f}".rstrip("0").rstrip(".")
    if abs_value >= 0.001:
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return f"{value:.3e}"


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
