"""波形配置页面。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop_app.app_state import AppState
from desktop_app.services.evaluation_service import EvaluationService, EvaluationServiceError
from radar_eval_core.schemas import EvaluationRequest, WaveformConfig


class WaveformPage(QWidget):
    """编辑 EvaluationRequest.waveform 的页面。"""

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        """初始化波形配置页面。"""
        super().__init__(parent)
        self._state = state
        self._service = EvaluationService()
        self.waveform_type = QComboBox()
        self.waveform_type.addItems(["rect", "lfm", "phase_code"])
        self.name = QLineEdit()
        self.carrier_frequency_hz = QLineEdit()
        self.bandwidth_hz = QLineEdit()
        self.pulse_width_s = QLineEdit()
        self.sample_rate_hz = QLineEdit()
        self.peak_power_w = QLineEdit()
        self.phase_code = QLineEdit()
        self._build_layout()
        self.waveform_type.currentTextChanged.connect(self._sync_phase_code_state)
        self.refresh_from_state()

    def refresh_from_state(self) -> None:
        """从 AppState 刷新表单。"""
        request = self._state.current_request or EvaluationRequest()
        waveform = request.waveform
        self.waveform_type.setCurrentText(waveform.waveform_type)
        self.name.setText(waveform.name)
        self.carrier_frequency_hz.setText(str(waveform.carrier_frequency_hz))
        self.bandwidth_hz.setText(str(waveform.bandwidth_hz))
        self.pulse_width_s.setText(str(waveform.pulse_width_s))
        self.sample_rate_hz.setText(str(waveform.sample_rate_hz))
        self.peak_power_w.setText(str(waveform.peak_power_w))
        phase_code_text = (
            "" if waveform.phase_code is None else ",".join(map(str, waveform.phase_code))
        )
        self.phase_code.setText(phase_code_text)
        self._sync_phase_code_state()

    def _build_layout(self) -> None:
        """构建更集中的波形配置布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(
            _header("波形配置", "设置复基带波形参数；页面只更新请求配置，不计算指标。"),
        )

        surface = QFrame()
        surface.setObjectName("PageSurface")
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(18, 18, 18, 18)
        surface_layout.setSpacing(16)

        panels = QHBoxLayout()
        panels.setSpacing(16)
        basic_panel, basic_form = _panel("基础参数")
        basic_form.addRow("波形类型", self.waveform_type)
        basic_form.addRow("名称", self.name)
        basic_form.addRow("载频 Hz", self.carrier_frequency_hz)
        basic_form.addRow("带宽 Hz", self.bandwidth_hz)

        timing_panel, timing_form = _panel("脉冲与采样")
        timing_form.addRow("脉宽 s", self.pulse_width_s)
        timing_form.addRow("采样率 Hz", self.sample_rate_hz)
        timing_form.addRow("峰值功率 W", self.peak_power_w)
        timing_form.addRow("相位码", self.phase_code)

        panels.addWidget(basic_panel)
        panels.addWidget(timing_panel)

        actions = QHBoxLayout()
        load_lfm_button = QPushButton("加载默认 LFM")
        apply_button = QPushButton("应用到当前请求")
        apply_button.setObjectName("PrimaryButton")
        load_lfm_button.clicked.connect(self._load_default_lfm)
        apply_button.clicked.connect(self._apply)
        actions.addStretch(1)
        actions.addWidget(load_lfm_button)
        actions.addWidget(apply_button)

        surface_layout.addLayout(panels)
        surface_layout.addLayout(actions)
        layout.addWidget(surface)
        layout.addStretch(1)

    def _sync_phase_code_state(self) -> None:
        """根据波形类型启用或禁用相位码输入框。"""
        is_phase_code = self.waveform_type.currentText() == "phase_code"
        self.phase_code.setEnabled(is_phase_code)
        self.phase_code.setPlaceholderText("例如: 1,1,1,-1,-1,1,-1" if is_phase_code else "")

    def _load_default_lfm(self) -> None:
        """加载默认 LFM 请求中的波形配置。"""
        try:
            request = self._service.load_request(Path("configs/lfm_default.json"))
        except EvaluationServiceError as exc:
            QMessageBox.critical(self, "加载失败", str(exc))
            return
        self._state.current_request = request
        self._state.dirty = True
        self.refresh_from_state()

    def _apply(self) -> None:
        """将表单内容应用到当前请求。"""
        try:
            waveform = WaveformConfig(
                waveform_type=self.waveform_type.currentText(),
                name=self.name.text().strip() or "default_waveform",
                carrier_frequency_hz=float(self.carrier_frequency_hz.text()),
                bandwidth_hz=float(self.bandwidth_hz.text()),
                pulse_width_s=float(self.pulse_width_s.text()),
                sample_rate_hz=float(self.sample_rate_hz.text()),
                peak_power_w=float(self.peak_power_w.text()),
                phase_code=(
                    _parse_phase_code(self.phase_code.text())
                    if self.waveform_type.currentText() == "phase_code"
                    else None
                ),
            )
            request = self._state.current_request or EvaluationRequest()
            self._state.current_request = request.model_copy(update={"waveform": waveform})
            self._state.dirty = True
            QMessageBox.information(self, "已应用", "波形配置已更新到当前请求。")
        except Exception as exc:
            QMessageBox.warning(self, "波形配置错误", str(exc))


def create_waveform_page(state: AppState | None = None) -> WaveformPage:
    """兼容旧入口，创建波形配置页面。"""
    return WaveformPage(state or AppState())


def _parse_phase_code(text: str) -> list[int] | None:
    """解析逗号分隔的相位编码。"""
    stripped = text.strip()
    if not stripped:
        return None
    return [int(item.strip()) for item in stripped.split(",") if item.strip()]


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


def _panel(title: str) -> tuple[QFrame, QFormLayout]:
    panel = QFrame()
    panel.setObjectName("SoftPanel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(14, 12, 14, 14)
    layout.setSpacing(10)
    title_label = QLabel(title)
    title_label.setObjectName("SectionTitle")
    form = QFormLayout()
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
    form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
    form.setHorizontalSpacing(14)
    form.setVerticalSpacing(9)
    layout.addWidget(title_label)
    layout.addLayout(form)
    return panel, form
