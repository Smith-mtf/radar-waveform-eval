"""配置化综合评分。"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .schemas import AxisScore, EvaluationRequest, EvaluationResult, MetricValue, RawMetric


class ScoringError(ValueError):
    """评分配置或评分输入不满足严格计算要求。"""


class MetricScoreConfig(BaseModel):
    """单个指标的评分配置。"""

    metric_id: str = Field(description="指标唯一标识")
    axis_id: str = Field(description="所属维度")
    direction: Literal["higher_better", "lower_better", "target_range"]
    min_value: float | None = Field(default=None, description="归一化下界")
    max_value: float | None = Field(default=None, description="归一化上界")
    target_min: float | None = Field(default=None, description="目标区间下界")
    target_max: float | None = Field(default=None, description="目标区间上界")
    weight: float = Field(default=1.0, gt=0, description="指标权重")
    enabled: bool = Field(default=True, description="是否启用")


class AxisScoreConfig(BaseModel):
    """评分维度配置。"""

    axis_id: str = Field(description="维度标识")
    display_name: str = Field(description="显示名称")
    weight: float = Field(default=1.0, gt=0, description="维度权重")
    enabled: bool = Field(default=True, description="是否启用")


class ScoringConfig(BaseModel):
    """完整评分配置。"""

    config_name: str = Field(default="default_scoring")
    metric_score_configs: list[MetricScoreConfig] = Field(default_factory=list)
    axis_score_configs: list[AxisScoreConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_axis_ids(self) -> ScoringConfig:
        """校验启用维度标识唯一。"""
        axis_ids = [axis.axis_id for axis in self.axis_score_configs]
        if len(axis_ids) != len(set(axis_ids)):
            raise ValueError("axis_score_configs 中 axis_id 不能重复。")
        return self


class MetricScoreResult(BaseModel):
    """单个指标归一化评分结果。"""

    metric_id: str
    axis_id: str
    raw_value: float | None = None
    normalized_score: float | None = Field(default=None, ge=0, le=100)
    weight: float = Field(gt=0)
    available: bool
    reason: str | None = None


def normalize_metric_value(value: float, config: MetricScoreConfig) -> float:
    """按配置方向将指标值归一化到 0 到 100。"""
    if not math.isfinite(value):
        raise ScoringError("value 必须是有限数值。")
    if config.direction == "higher_better":
        score = _normalize_higher_better(value, config)
    elif config.direction == "lower_better":
        score = _normalize_lower_better(value, config)
    elif config.direction == "target_range":
        score = _normalize_target_range(value, config)
    else:
        raise ScoringError(f"不支持的评分方向: {config.direction}")
    return float(min(100.0, max(0.0, score)))


def compute_axis_scores(
    raw_metrics: Sequence[RawMetric],
    scoring_config: ScoringConfig,
) -> list[AxisScore]:
    """根据启用指标的加权平均计算各维度得分；无可用指标时返回 unavailable。"""
    raw_metric_by_id = {metric.metric_id: metric for metric in raw_metrics}
    axis_scores: list[AxisScore] = []
    for axis_config in scoring_config.axis_score_configs:
        if not axis_config.enabled:
            continue
        metric_results = _score_metrics_for_axis(
            axis_config.axis_id,
            raw_metric_by_id,
            scoring_config,
        )
        available_results = [
            result
            for result in metric_results
            if result.available and result.normalized_score is not None
        ]
        if not available_results:
            axis_scores.append(
                AxisScore(
                    axis_id=axis_config.axis_id,
                    name=axis_config.display_name,
                    score=None,
                    available=False,
                    reason="该维度没有可用评分指标。",
                    metrics=[],
                ),
            )
            continue

        total_weight = sum(result.weight for result in available_results)
        if total_weight <= 0:
            raise ScoringError(f"axis {axis_config.axis_id} 的可用指标总权重必须大于 0。")
        axis_score = sum(
            result.normalized_score * result.weight for result in available_results
        ) / total_weight
        axis_scores.append(
            AxisScore(
                axis_id=axis_config.axis_id,
                name=axis_config.display_name,
                score=float(axis_score),
                available=True,
                metrics=[
                    MetricValue(
                        name=result.metric_id,
                        value=float(result.normalized_score),
                        unit="score",
                        description="归一化指标得分",
                    )
                    for result in available_results
                ],
            ),
        )
    return axis_scores


def compute_total_score(
    axis_scores: Sequence[AxisScore],
    scoring_config: ScoringConfig,
) -> float:
    """根据可用维度的权重计算总分；没有可用维度时抛错。"""
    axis_score_by_id = {axis.axis_id: axis for axis in axis_scores}
    weighted_sum = 0.0
    total_weight = 0.0
    for axis_config in scoring_config.axis_score_configs:
        if not axis_config.enabled:
            continue
        axis_score = axis_score_by_id.get(axis_config.axis_id)
        if axis_score is None or not axis_score.available or axis_score.score is None:
            continue
        weighted_sum += axis_score.score * axis_config.weight
        total_weight += axis_config.weight

    if total_weight <= 0:
        raise ScoringError("没有可用于计算总分的维度。")
    return float(weighted_sum / total_weight)


def evaluate_request(request: EvaluationRequest) -> EvaluationResult:
    """保留旧入口；请调用 evaluation_pipeline.compute_waveform_evaluation。"""
    _ = request
    raise NotImplementedError("请使用 compute_waveform_evaluation。")


def _score_metrics_for_axis(
    axis_id: str,
    raw_metric_by_id: dict[str, RawMetric],
    scoring_config: ScoringConfig,
) -> list[MetricScoreResult]:
    """计算单个维度下所有启用指标的评分结果。"""
    results: list[MetricScoreResult] = []
    for metric_config in scoring_config.metric_score_configs:
        if not metric_config.enabled or metric_config.axis_id != axis_id:
            continue
        raw_metric = raw_metric_by_id.get(metric_config.metric_id)
        if raw_metric is None:
            results.append(
                MetricScoreResult(
                    metric_id=metric_config.metric_id,
                    axis_id=axis_id,
                    weight=metric_config.weight,
                    available=False,
                    reason="未找到该指标。",
                ),
            )
            continue
        if not raw_metric.available or raw_metric.value is None:
            results.append(
                MetricScoreResult(
                    metric_id=metric_config.metric_id,
                    axis_id=axis_id,
                    raw_value=raw_metric.value,
                    weight=metric_config.weight,
                    available=False,
                    reason=raw_metric.reason or "指标不可用。",
                ),
            )
            continue
        normalized_score = normalize_metric_value(raw_metric.value, metric_config)
        results.append(
            MetricScoreResult(
                metric_id=metric_config.metric_id,
                axis_id=axis_id,
                raw_value=raw_metric.value,
                normalized_score=normalized_score,
                weight=metric_config.weight,
                available=True,
            ),
        )
    return results


def _normalize_higher_better(value: float, config: MetricScoreConfig) -> float:
    """高值更优的线性归一化。"""
    min_value, max_value = _require_min_max(config)
    if value <= min_value:
        return 0.0
    if value >= max_value:
        return 100.0
    return 100.0 * (value - min_value) / (max_value - min_value)


def _normalize_lower_better(value: float, config: MetricScoreConfig) -> float:
    """低值更优的线性归一化。"""
    min_value, max_value = _require_min_max(config)
    if value <= min_value:
        return 100.0
    if value >= max_value:
        return 0.0
    return 100.0 * (max_value - value) / (max_value - min_value)


def _normalize_target_range(value: float, config: MetricScoreConfig) -> float:
    """目标区间内为满分、区间外线性下降的归一化。"""
    min_value, max_value = _require_min_max(config)
    target_min = _require_finite(config.target_min, "target_min")
    target_max = _require_finite(config.target_max, "target_max")
    if not min_value < target_min <= target_max < max_value:
        raise ScoringError("target_range 要求 min_value < target_min <= target_max < max_value。")
    if target_min <= value <= target_max:
        return 100.0
    if value < target_min:
        if value <= min_value:
            return 0.0
        return 100.0 * (value - min_value) / (target_min - min_value)
    if value >= max_value:
        return 0.0
    return 100.0 * (max_value - value) / (max_value - target_max)


def _require_min_max(config: MetricScoreConfig) -> tuple[float, float]:
    """读取并校验 min_value / max_value。"""
    min_value = _require_finite(config.min_value, "min_value")
    max_value = _require_finite(config.max_value, "max_value")
    if max_value <= min_value:
        raise ScoringError("max_value 必须大于 min_value。")
    return min_value, max_value


def _require_finite(value: float | None, name: str) -> float:
    """校验配置值存在且有限。"""
    if value is None or not math.isfinite(value):
        raise ScoringError(f"{name} 必须是有限数值。")
    return float(value)
