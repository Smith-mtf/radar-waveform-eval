"""桌面端模块导入与主窗口基础 smoke test。"""

from __future__ import annotations

import importlib
import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QSplitter, QTabWidget

from desktop_app.app_state import AppState
from desktop_app.windows.main_window import (
    ChartPanel,
    LeftParameterPanel,
    MainWindow,
    RadarChartWidget,
    _ambiguity_db_image,
    _ambiguity_surface_colors,
    _normalized_surface_axis,
)
from radar_eval_core.schemas import EvaluationRequest


def test_desktop_modules_can_be_imported() -> None:
    """测试桌面端关键模块可以导入。"""
    module_names = [
        "desktop_app.main",
        "desktop_app.windows.main_window",
        "desktop_app.services.evaluation_service",
        "desktop_app.services.export_service",
        "desktop_app.services.project_service",
        "desktop_app.services.report_service",
        "desktop_app.version",
        "desktop_app.workers.evaluation_worker",
    ]

    for module_name in module_names:
        assert importlib.import_module(module_name) is not None


def test_main_window_shell_smoke() -> None:
    """测试主界面能创建，并包含主要布局元素。"""
    app = QApplication.instance() or QApplication([])
    _ = app
    window = MainWindow(AppState(current_request=EvaluationRequest()))

    assert window.windowTitle() == "雷达波形性能评估软件 V1.0"
    assert window.findChild(QSplitter) is not None
    assert window.findChild(RadarChartWidget) is not None
    tab_widget = window.findChild(QTabWidget)
    assert tab_widget is not None
    assert tab_widget.count() == 2
    assert any(
        button.objectName() == "RunButton"
        for button in window.findChildren(QPushButton)
    )


def test_waveform_parameter_visibility_follows_waveform_type() -> None:
    """测试波形参数控件按波形类型隐藏不适用项。"""
    app = QApplication.instance() or QApplication([])
    _ = app
    panel = LeftParameterPanel()

    panel.waveform_type_combo.setCurrentText("rect")
    assert panel.bandwidth_mhz.isHidden()
    assert panel.phase_code_edit.isHidden()
    assert not panel.derived_bandwidth_label.isHidden()

    panel.waveform_type_combo.setCurrentText("lfm")
    assert not panel.bandwidth_mhz.isHidden()
    assert panel.phase_code_edit.isHidden()
    assert panel.derived_bandwidth_label.isHidden()

    panel.waveform_type_combo.setCurrentText("phase_code")
    assert panel.bandwidth_mhz.isHidden()
    assert not panel.phase_code_edit.isHidden()
    assert not panel.derived_bandwidth_label.isHidden()


def test_derived_bandwidth_label_updates_for_phase_code() -> None:
    """测试 phase_code 派生带宽按子脉冲宽度刷新。"""
    app = QApplication.instance() or QApplication([])
    _ = app
    panel = LeftParameterPanel()

    panel.waveform_type_combo.setCurrentText("phase_code")
    pulse_width_label = panel._waveform_row_labels[panel.pulse_width_us]
    assert pulse_width_label.text() == "子脉冲宽度"

    panel.pulse_width_us.setValue(50.0)
    panel.phase_code_edit.setText("1,1,1,-1,-1,1,-1,1,-1,1")
    assert panel.derived_bandwidth_label.text() == "20 kHz"

    panel.phase_code_edit.setText("1,-1")
    assert panel.derived_bandwidth_label.text() == "20 kHz"

    panel.waveform_type_combo.setCurrentText("lfm")
    assert pulse_width_label.text() == "脉宽"


def test_ambiguity_surface_db_rendering_smoke() -> None:
    """测试模糊函数热力图 dB 转换和绘制入口可处理零值。"""
    app = QApplication.instance() or QApplication([])
    _ = app
    matrix = np.array([[1.0, 0.0], [0.25, 0.0]], dtype=float)

    image_db = _ambiguity_db_image(matrix)
    colors = _ambiguity_surface_colors(image_db.T)
    chart = ChartPanel("test", preload_gl=True)
    outer_layout_count = chart.layout().count()
    stack_count = chart._content_stack.count()
    gl_was_preloaded = chart._gl_widget is not None
    chart.plot_ambiguity_surface(
        [-1.0, 1.0],
        [-100.0, 100.0],
        matrix.tolist(),
        x_label="Delay us",
    )

    assert np.max(image_db) == 0.0
    assert np.min(image_db) >= -60.0
    assert colors.shape == (matrix.size, 4)
    normalized_axis = _normalized_surface_axis(np.array([-2.0, 0.0, 2.0]))
    assert np.allclose(normalized_axis, np.array([-1.0, 0.0, 1.0]))
    assert chart.layout().count() == outer_layout_count
    if gl_was_preloaded:
        assert chart._content_stack.count() == stack_count
    assert not hasattr(chart, "plot_heatmap")
