"""桌面端评估服务。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from radar_eval_core.evaluation_pipeline import (
    EvaluationPipelineError,
    compute_waveform_evaluation,
)
from radar_eval_core.schemas import (
    EvaluationRequest,
    EvaluationResult,
    ScenarioEnvironmentConfig,
    apply_scenario_environment_config,
)
from radar_eval_core.scoring import ScoringConfig


class EvaluationServiceError(RuntimeError):
    """桌面评估服务错误。"""


class EvaluationService:
    """封装桌面端对算法评估流水线的调用。"""

    def load_request(self, path: Path) -> EvaluationRequest:
        """从 JSON 文件读取 EvaluationRequest。"""
        try:
            return EvaluationRequest.model_validate(_read_json(path))
        except Exception as exc:
            raise EvaluationServiceError(f"读取评估请求失败: {exc}") from exc

    def load_request_with_scenario_environment(
        self,
        request_path: Path,
        scenario_environment_path: Path,
    ) -> EvaluationRequest:
        """读取波形/请求配置，并应用独立场景与环境配置。"""
        request = self.load_request(request_path)
        scenario_environment = self.load_scenario_environment_config(scenario_environment_path)
        return self.apply_scenario_environment_config(request, scenario_environment)

    def load_scoring_config(self, path: Path) -> ScoringConfig:
        """从 JSON 文件读取 ScoringConfig。"""
        try:
            return ScoringConfig.model_validate(_read_json(path))
        except Exception as exc:
            raise EvaluationServiceError(f"读取评分配置失败: {exc}") from exc

    def load_scenario_environment_config(self, path: Path) -> ScenarioEnvironmentConfig:
        """从 JSON 文件读取独立场景与环境配置。"""
        try:
            return ScenarioEnvironmentConfig.model_validate(_read_json(path))
        except Exception as exc:
            raise EvaluationServiceError(f"读取场景与环境配置失败: {exc}") from exc

    def apply_scenario_environment_config(
        self,
        request: EvaluationRequest,
        scenario_environment: ScenarioEnvironmentConfig,
    ) -> EvaluationRequest:
        """把独立场景与环境配置合并到现有请求，保留波形配置。"""
        try:
            return apply_scenario_environment_config(request, scenario_environment)
        except Exception as exc:
            raise EvaluationServiceError(f"应用场景与环境配置失败: {exc}") from exc

    def evaluate(
        self,
        request: EvaluationRequest,
        scoring_config: ScoringConfig,
    ) -> EvaluationResult:
        """调用 radar_eval_core 完成评估。"""
        try:
            return compute_waveform_evaluation(request, scoring_config)
        except EvaluationPipelineError as exc:
            raise EvaluationServiceError(f"评估失败: {exc}") from exc
        except Exception as exc:
            raise EvaluationServiceError(f"评估服务异常: {exc}") from exc


def submit_evaluation(
    request: EvaluationRequest,
    scoring_config: ScoringConfig,
) -> EvaluationResult:
    """兼容旧入口，执行一次评估。"""
    return EvaluationService().evaluate(request, scoring_config)


def _read_json(path: Path) -> Any:
    """读取 UTF-8 JSON 文件。"""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)
