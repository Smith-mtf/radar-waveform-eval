"""综合评分相关占位接口。"""

from __future__ import annotations

from .schemas import EvaluationRequest, EvaluationResult


def evaluate_request(request: EvaluationRequest) -> EvaluationResult:
    """执行综合评估的占位函数。"""
    _ = request
    # TODO: 汇总探测、抗干扰、反侦察和工程可实现性指标。
    raise NotImplementedError("综合评分将在后续版本实现。")

