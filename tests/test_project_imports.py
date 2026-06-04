"""项目基础导入测试。"""

from __future__ import annotations

import importlib


def test_core_schemas_can_be_imported() -> None:
    """测试核心数据结构模块可以导入。"""
    module = importlib.import_module("radar_eval_core.schemas")

    assert module is not None


def test_desktop_main_can_be_imported() -> None:
    """测试桌面应用入口模块可以导入。"""
    module = importlib.import_module("desktop_app.main")

    assert module is not None

