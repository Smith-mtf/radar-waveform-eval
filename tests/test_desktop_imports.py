"""桌面端模块导入测试。"""

from __future__ import annotations

import importlib


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
