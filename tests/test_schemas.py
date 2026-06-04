"""数据结构测试。"""

from __future__ import annotations

from radar_eval_core.schemas import EvaluationRequest


def test_create_minimal_evaluation_request() -> None:
    """测试可以创建最小评估请求。"""
    request = EvaluationRequest()

    assert request.waveform.name == "default_lfm"
    assert request.scenario.name == "default_scenario"
    assert request.jammer.enabled is False

