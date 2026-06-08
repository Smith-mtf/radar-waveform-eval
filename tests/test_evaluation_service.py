"""桌面评估服务测试。"""

from __future__ import annotations

from pathlib import Path

from desktop_app.services.evaluation_service import EvaluationService
from radar_eval_core.schemas import EvaluationResult

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_evaluation_service_runs_default_lfm_config() -> None:
    """测试评估服务可以运行默认 LFM 配置。"""
    service = EvaluationService()
    request = service.load_request(PROJECT_ROOT / "configs" / "lfm_default.json")
    scoring_config = service.load_scoring_config(
        PROJECT_ROOT / "configs" / "scoring_default.json",
    )

    result = service.evaluate(request, scoring_config)

    assert isinstance(result, EvaluationResult)
    assert len(result.axis_scores) == 6
    assert result.raw_metrics


def test_evaluation_service_does_not_import_pyside6() -> None:
    """测试评估服务不直接依赖 PySide6。"""
    source = (PROJECT_ROOT / "desktop_app" / "services" / "evaluation_service.py").read_text(
        encoding="utf-8",
    )

    assert "PySide6" not in source
