"""桌面项目文件服务。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from desktop_app.app_state import AppState
from radar_eval_core.schemas import EvaluationRequest, EvaluationResult
from radar_eval_core.scoring import ScoringConfig

PROJECT_FILE_SUFFIX = ".rwep.json"


class ProjectServiceError(RuntimeError):
    """项目文件读取或保存错误。"""


class ProjectService:
    """保存和加载本地 JSON 项目文件。"""

    def save_project(self, state: AppState, path: Path) -> Path:
        """将当前 AppState 保存为项目 JSON 文件。"""
        if state.current_request is None:
            raise ProjectServiceError("当前没有 EvaluationRequest，无法保存项目。")
        if state.current_scoring_config is None:
            raise ProjectServiceError("当前没有 ScoringConfig，无法保存项目。")

        output_path = _ensure_project_suffix(path)
        payload: dict[str, Any] = {
            "request": state.current_request.model_dump(mode="json"),
            "scoring_config": state.current_scoring_config.model_dump(mode="json"),
            "result": None
            if state.current_result is None
            else state.current_result.model_dump(mode="json"),
            "comparison_results": [
                result.model_dump(mode="json") for result in state.comparison_results
            ],
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.write("\n")
        state.current_project_path = output_path
        state.dirty = False
        return output_path

    def open_project(self, path: Path) -> AppState:
        """从项目 JSON 文件恢复 AppState。"""
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except Exception as exc:
            raise ProjectServiceError(f"读取项目文件失败: {exc}") from exc

        if not isinstance(payload, dict):
            raise ProjectServiceError("项目文件顶层必须是 JSON object。")
        if "request" not in payload or "scoring_config" not in payload:
            raise ProjectServiceError("项目文件必须包含 request 和 scoring_config。")

        try:
            request = EvaluationRequest.model_validate(payload["request"])
            scoring_config = ScoringConfig.model_validate(payload["scoring_config"])
            result = (
                None
                if payload.get("result") is None
                else EvaluationResult.model_validate(payload["result"])
            )
            comparison_results = [
                EvaluationResult.model_validate(item)
                for item in payload.get("comparison_results", [])
            ]
        except Exception as exc:
            raise ProjectServiceError(f"项目文件内容无效: {exc}") from exc

        return AppState(
            current_project_path=path,
            current_request=request,
            current_scoring_config=scoring_config,
            current_result=result,
            comparison_results=comparison_results,
            dirty=False,
        )


def load_project(path: Path) -> AppState:
    """兼容旧入口，加载项目文件。"""
    return ProjectService().open_project(path)


def save_project(state: AppState, path: Path) -> Path:
    """兼容旧入口，保存项目文件。"""
    return ProjectService().save_project(state, path)


def _ensure_project_suffix(path: Path) -> Path:
    """确保项目文件扩展名为 .rwep.json。"""
    if path.name.endswith(PROJECT_FILE_SUFFIX):
        return path
    return path.with_name(f"{path.name}{PROJECT_FILE_SUFFIX}")
