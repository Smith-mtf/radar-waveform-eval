"""桌面端评估服务。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from radar_eval_core.evaluation_pipeline import (
    EvaluationPipelineError,
    compute_waveform_evaluation,
)
from radar_eval_core.schemas import EvaluationRequest, EvaluationResult
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

    def load_scoring_config(self, path: Path) -> ScoringConfig:
        """从 JSON 文件读取 ScoringConfig。"""
        try:
            return ScoringConfig.model_validate(_read_json(path))
        except Exception as exc:
            raise EvaluationServiceError(f"读取评分配置失败: {exc}") from exc

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
