"""桌面应用装配。"""

from __future__ import annotations

from pathlib import Path

from matplotlib import rcParams
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from desktop_app.app_state import AppState
from desktop_app.services.evaluation_service import EvaluationService
from desktop_app.ui_theme import APP_STYLESHEET
from desktop_app.windows.main_window import MainWindow
from radar_eval_core.schemas import EvaluationRequest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUEST_PATH = PROJECT_ROOT / "configs" / "lfm_default.json"
DEFAULT_SCORING_PATH = PROJECT_ROOT / "configs" / "scoring_default.json"


def configure_application() -> None:
    """配置桌面应用全局行为。"""
    app = QApplication.instance()
    if app is not None:
        app.setStyle("Fusion")
        app.setFont(QFont("Microsoft YaHei UI", 9))
        app.setStyleSheet(APP_STYLESHEET)
    rcParams["font.sans-serif"] = [
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "SimHei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    rcParams["axes.unicode_minus"] = False


def create_initial_state() -> tuple[AppState, list[str]]:
    """创建启动时的 AppState，并尽量加载默认配置。"""
    service = EvaluationService()
    state = AppState(current_request=EvaluationRequest())
    errors: list[str] = []
    try:
        state.current_request = service.load_request(DEFAULT_REQUEST_PATH)
    except Exception as exc:
        errors.append(str(exc))
    try:
        state.current_scoring_config = service.load_scoring_config(DEFAULT_SCORING_PATH)
    except Exception as exc:
        errors.append(str(exc))
    state.dirty = False
    return state, errors


def create_main_window() -> tuple[MainWindow, list[str]]:
    """创建加载默认状态的主窗口。"""
    state, errors = create_initial_state()
    return MainWindow(state), errors
