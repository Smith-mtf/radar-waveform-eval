"""评估服务占位模块。"""

from __future__ import annotations

from radar_eval_core.schemas import EvaluationRequest


def submit_evaluation(request: EvaluationRequest) -> None:
    """提交评估请求的占位函数。"""
    _ = request
    # TODO: 后续调用 radar_eval_core 完成评估。
    return None

