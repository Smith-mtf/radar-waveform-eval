"""项目文件服务测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from desktop_app.app_state import AppState
from desktop_app.services.evaluation_service import EvaluationService
from desktop_app.services.project_service import ProjectService, ProjectServiceError

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_save_and_open_project_json(tmp_path: Path) -> None:
    """测试保存和打开 .rwep.json 项目文件。"""
    evaluation_service = EvaluationService()
    project_service = ProjectService()
    request = evaluation_service.load_request(PROJECT_ROOT / "configs" / "lfm_default.json")
    scoring_config = evaluation_service.load_scoring_config(
        PROJECT_ROOT / "configs" / "scoring_default.json",
    )
    result = evaluation_service.evaluate(request, scoring_config)
    state = AppState(
        current_request=request,
        current_scoring_config=scoring_config,
        current_result=result,
        dirty=True,
    )

    saved_path = project_service.save_project(state, tmp_path / "case")
    loaded_state = project_service.open_project(saved_path)
    payload = json.loads(saved_path.read_text(encoding="utf-8"))

    assert saved_path.name.endswith(".rwep.json")
    assert "comparison_results" not in payload
    assert loaded_state.current_request is not None
    assert loaded_state.current_request.waveform.name == "default_lfm"
    assert loaded_state.current_scoring_config is not None
    assert loaded_state.current_result is not None
    assert loaded_state.dirty is False


def test_open_project_rejects_invalid_json(tmp_path: Path) -> None:
    """测试无效 JSON 项目文件会报错。"""
    path = tmp_path / "invalid.rwep.json"
    path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ProjectServiceError):
        ProjectService().open_project(path)


def test_open_project_rejects_missing_required_fields(tmp_path: Path) -> None:
    """测试缺少必要字段的项目文件会报错。"""
    path = tmp_path / "missing.rwep.json"
    path.write_text(json.dumps({"request": {}}), encoding="utf-8")

    with pytest.raises(ProjectServiceError):
        ProjectService().open_project(path)

