"""版本信息测试。"""

from __future__ import annotations

from desktop_app.version import APP_NAME, APP_STAGE, APP_VERSION


def test_version_constants_exist() -> None:
    """测试版本常量存在且非空。"""
    assert APP_NAME
    assert APP_VERSION
    assert APP_STAGE

