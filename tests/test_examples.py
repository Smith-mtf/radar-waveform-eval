"""示例项目测试。"""

from __future__ import annotations

from pathlib import Path

from desktop_app.services.project_service import ProjectService

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_lfm_example_project_can_be_opened() -> None:
    """测试 LFM 示例项目可由 ProjectService 打开。"""
    state = ProjectService().open_project(PROJECT_ROOT / "examples" / "lfm_example.rwep.json")

    assert state.current_request is not None
    assert state.current_request.waveform.name == "example_lfm"
    assert state.current_scoring_config is not None


def test_phase_code_example_project_can_be_opened() -> None:
    """测试相位编码示例项目可由 ProjectService 打开。"""
    state = ProjectService().open_project(
        PROJECT_ROOT / "examples" / "phase_code_example.rwep.json",
    )

    assert state.current_request is not None
    assert state.current_request.waveform.name == "example_phase_code"
    assert state.current_scoring_config is not None

