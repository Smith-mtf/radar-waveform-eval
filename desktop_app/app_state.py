"""桌面端共享应用状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from radar_eval_core.schemas import EvaluationRequest, EvaluationResult
from radar_eval_core.scoring import ScoringConfig


@dataclass(slots=True)
class AppState:
    """在主窗口、页面和服务之间共享的状态容器。"""

    current_project_path: Path | None = None
    current_request: EvaluationRequest | None = None
    current_scoring_config: ScoringConfig | None = None
    current_result: EvaluationResult | None = None
    comparison_results: list[EvaluationResult] = field(default_factory=list)
    dirty: bool = False
