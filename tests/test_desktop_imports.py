"""桌面端模块导入与主窗口框架测试。"""

from __future__ import annotations

import importlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QSplitter, QTabWidget

from desktop_app.app_state import AppState
from desktop_app.windows.main_window import MainWindow
from radar_eval_core.schemas import EvaluationRequest


def test_desktop_modules_can_be_imported() -> None:
    """测试桌面闭环关键模块可以导入。"""
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
    """测试新的单文件主界面框架可以创建，并包含核心布局部件。"""
    app = QApplication.instance() or QApplication([])
    _ = app
    window = MainWindow(AppState(current_request=EvaluationRequest()))

    assert window.windowTitle() == "雷达波形性能评估软件 V1.0"
    assert window.findChild(QSplitter) is not None
    tab_widget = window.findChild(QTabWidget)
    assert tab_widget is not None
    assert tab_widget.count() == 2
    run_buttons = [
        button
        for button in window.findChildren(QPushButton)
        if button.objectName() == "RunButton"
    ]
    assert run_buttons
