"""场景与评估参数配置页面。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop_app.app_state import AppState
from radar_eval_core.schemas import (
    EvaluationRequest,
    EvaluationSettings,
    JammerConfig,
    ScenarioConfig,
)


class ScenarioPage(QWidget):
    """编辑 scenario、jammer 和 evaluation 参数的页面。"""

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        """初始化场景配置页面。"""
        super().__init__(parent)
        self._state = state
        self.target_range_m = QLineEdit()
        self.target_radial_velocity_mps = QLineEdit()
        self.input_snr_db = QLineEdit()
        self.noise_variance = QLineEdit()
        self.pfa = QLineEdit()
        self.target_pd = QLineEdit()
        self.jammer_enabled = QCheckBox("启用宽带高斯噪声压制干扰")
        self.jsr_db = QLineEdit()
        self.occupied_power_fraction = QLineEdit()
        self.prf_hz = QLineEdit()
        self.pri_s = QLineEdit()
        self.num_pulses = QLineEdit()
        self.cpi_s = QLineEdit()
        self._build_layout()
        self.refresh_from_state()

    def refresh_from_state(self) -> None:
        """从 AppState 刷新表单。"""
        request = self._state.current_request or EvaluationRequest()
        scenario = request.scenario
        jammer = request.jammer
        evaluation = request.evaluation
        self.target_range_m.setText(str(scenario.target_range_m))
        self.target_radial_velocity_mps.setText(str(scenario.target_radial_velocity_mps))
        self.input_snr_db.setText(str(scenario.signal_to_noise_ratio_db))
        self.noise_variance.setText(str(evaluation.noise_variance))
        self.pfa.setText(str(evaluation.pfa))
        self.target_pd.setText("" if evaluation.target_pd is None else str(evaluation.target_pd))
        self.jammer_enabled.setChecked(jammer.enabled)
        self.jsr_db.setText(str(jammer.jammer_to_signal_ratio_db))
        self.occupied_power_fraction.setText(str(evaluation.occupied_power_fraction))
        self.prf_hz.setText("" if evaluation.prf_hz is None else str(evaluation.prf_hz))
        self.pri_s.setText("" if evaluation.pri_s is None else str(evaluation.pri_s))
        self.num_pulses.setText("" if evaluation.num_pulses is None else str(evaluation.num_pulses))
        self.cpi_s.setText("" if evaluation.cpi_s is None else str(evaluation.cpi_s))

    def _build_layout(self) -> None:
        """构建分组后的场景配置布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(_header("场景配置", "设置当前评估请求支持的场景、检测、干扰和 LPI 参数。"))

        surface = QFrame()
        surface.setObjectName("PageSurface")
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(18, 18, 18, 18)
        surface_layout.setSpacing(16)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        target_panel, target_form = _panel("目标与噪声")
        target_form.addRow("目标距离 m", self.target_range_m)
        target_form.addRow("径向速度 m/s", self.target_radial_velocity_mps)
        target_form.addRow("输入 SNR dB", self.input_snr_db)
        target_form.addRow("噪声方差", self.noise_variance)

        detection_panel, detection_form = _panel("检测与相干处理")
        detection_form.addRow("Pfa", self.pfa)
        detection_form.addRow("目标 Pd", self.target_pd)
        detection_form.addRow("PRF Hz", self.prf_hz)
        detection_form.addRow("PRI s", self.pri_s)
        detection_form.addRow("脉冲数", self.num_pulses)
        detection_form.addRow("CPI s", self.cpi_s)

        jamming_panel, jamming_form = _panel("干扰与 LPI")
        jamming_form.addRow("干扰模型", self.jammer_enabled)
        jamming_form.addRow("JSR dB", self.jsr_db)
        jamming_form.addRow("占用功率比例", self.occupied_power_fraction)

        grid.addWidget(target_panel, 0, 0)
        grid.addWidget(detection_panel, 0, 1)
        grid.addWidget(jamming_panel, 1, 0, 1, 2)

        apply_button = QPushButton("应用到当前请求")
        apply_button.setObjectName("PrimaryButton")
        apply_button.clicked.connect(self._apply)

        surface_layout.addLayout(grid)
        surface_layout.addWidget(apply_button, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(surface)
        layout.addStretch(1)

    def _apply(self) -> None:
        """将表单内容应用到当前请求。"""
        try:
            scenario = ScenarioConfig(
                target_range_m=float(self.target_range_m.text()),
                target_radial_velocity_mps=float(self.target_radial_velocity_mps.text()),
                signal_to_noise_ratio_db=float(self.input_snr_db.text()),
            )
            jammer = JammerConfig(
                enabled=self.jammer_enabled.isChecked(),
                jammer_type="noise" if self.jammer_enabled.isChecked() else "none",
                jammer_to_signal_ratio_db=float(self.jsr_db.text()),
            )
            current = self._state.current_request or EvaluationRequest()
            evaluation = EvaluationSettings(
                pfa=float(self.pfa.text()),
                target_pd=_parse_optional_float(self.target_pd.text()),
                noise_variance=float(self.noise_variance.text()),
                mainlobe_spec=current.evaluation.mainlobe_spec,
                doppler_max_hz=current.evaluation.doppler_max_hz,
                doppler_points=current.evaluation.doppler_points,
                doppler_loss_db=current.evaluation.doppler_loss_db,
                cpi_s=_parse_optional_float(self.cpi_s.text()),
                num_pulses=_parse_optional_int(self.num_pulses.text()),
                prf_hz=_parse_optional_float(self.prf_hz.text()),
                pri_s=_parse_optional_float(self.pri_s.text()),
                occupied_power_fraction=float(self.occupied_power_fraction.text()),
            )
            self._state.current_request = current.model_copy(
                update={
                    "scenario": scenario,
                    "jammer": jammer,
                    "evaluation": evaluation,
                },
            )
            self._state.dirty = True
            QMessageBox.information(self, "已应用", "场景配置已更新到当前请求。")
        except Exception as exc:
            QMessageBox.warning(self, "场景配置错误", str(exc))


def create_scenario_page(state: AppState | None = None) -> ScenarioPage:
    """兼容旧入口，创建场景配置页面。"""
    return ScenarioPage(state or AppState())


def _parse_optional_float(text: str) -> float | None:
    """解析可为空的 float 字段。"""
    stripped = text.strip()
    return None if not stripped else float(stripped)


def _parse_optional_int(text: str) -> int | None:
    """解析可为空的 int 字段。"""
    stripped = text.strip()
    return None if not stripped else int(stripped)


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

