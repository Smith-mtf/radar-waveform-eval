"""后台评估 worker。"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from desktop_app.services.evaluation_service import EvaluationService, EvaluationServiceError
from radar_eval_core.schemas import EvaluationRequest, EvaluationResult
from radar_eval_core.scoring import ScoringConfig


class EvaluationWorker(QObject):
    """在 QThread 中运行算法评估的 worker。"""

    started = Signal()
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        request: EvaluationRequest,
        scoring_config: ScoringConfig,
        service: EvaluationService | None = None,
    ) -> None:
        """初始化 worker。"""
        super().__init__()
        self._request = request
        self._scoring_config = scoring_config
        self._service = service or EvaluationService()

    @Slot()
    def run(self) -> None:
        """执行评估并通过 signal 返回结果。"""
        self.started.emit()
        try:
            result: EvaluationResult = self._service.evaluate(
                self._request,
                self._scoring_config,
            )
        except EvaluationServiceError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"评估任务异常: {exc}")
        else:
            self.finished.emit(result)


def run_evaluation_worker() -> None:
    """保留旧占位入口；请实例化 EvaluationWorker 并放入 QThread。"""
    raise NotImplementedError("请使用 EvaluationWorker。")
