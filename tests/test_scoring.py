"""配置化评分测试。"""

from __future__ import annotations

import pytest

from radar_eval_core.schemas import RawMetric
from radar_eval_core.scoring import (
    AxisScoreConfig,
    MetricScoreConfig,
    ScoringConfig,
    ScoringError,
    compute_axis_scores,
    compute_total_score,
    normalize_metric_value,
)


def test_normalize_higher_better() -> None:
    """测试高值更优归一化。"""
    config = MetricScoreConfig(
        metric_id="m",
        axis_id="a",
        direction="higher_better",
        min_value=0.0,
        max_value=10.0,
    )

    assert normalize_metric_value(5.0, config) == pytest.approx(50.0)
    assert normalize_metric_value(20.0, config) == pytest.approx(100.0)


def test_normalize_lower_better() -> None:
    """测试低值更优归一化。"""
    config = MetricScoreConfig(
        metric_id="m",
        axis_id="a",
        direction="lower_better",
        min_value=0.0,
        max_value=10.0,
    )

    assert normalize_metric_value(2.0, config) == pytest.approx(80.0)
    assert normalize_metric_value(-1.0, config) == pytest.approx(100.0)


def test_normalize_target_range() -> None:
    """测试目标区间归一化。"""
    config = MetricScoreConfig(
        metric_id="m",
        axis_id="a",
        direction="target_range",
        min_value=0.0,
        target_min=4.0,
        target_max=6.0,
        max_value=10.0,
    )

    assert normalize_metric_value(5.0, config) == pytest.approx(100.0)
    assert normalize_metric_value(2.0, config) == pytest.approx(50.0)
    assert normalize_metric_value(8.0, config) == pytest.approx(50.0)


def test_invalid_bounds_raise() -> None:
    """测试非法边界报错。"""
    config = MetricScoreConfig(
        metric_id="m",
        axis_id="a",
        direction="higher_better",
        min_value=10.0,
        max_value=0.0,
    )

    with pytest.raises(ScoringError):
        normalize_metric_value(5.0, config)


def test_axis_weighted_average_and_unavailable_metrics() -> None:
    """测试维度加权平均会跳过不可用指标。"""
    scoring_config = ScoringConfig(
        metric_score_configs=[
            MetricScoreConfig(
                metric_id="a.good",
                axis_id="a",
                direction="higher_better",
                min_value=0.0,
                max_value=10.0,
                weight=2.0,
            ),
            MetricScoreConfig(
                metric_id="a.missing",
                axis_id="a",
                direction="higher_better",
                min_value=0.0,
                max_value=10.0,
                weight=1.0,
            ),
        ],
        axis_score_configs=[AxisScoreConfig(axis_id="a", display_name="A", weight=1.0)],
    )
    raw_metrics = [
        RawMetric(metric_id="a.good", axis_id="a", value=5.0, available=True),
        RawMetric(metric_id="a.missing", axis_id="a", value=None, available=False, reason="无参数"),
    ]

    axis_scores = compute_axis_scores(raw_metrics, scoring_config)

    assert axis_scores[0].available is True
    assert axis_scores[0].score == pytest.approx(50.0)


def test_axis_without_available_metrics_is_unavailable() -> None:
    """测试没有可用指标的维度不会得到伪造 0 分。"""
    scoring_config = ScoringConfig(
        metric_score_configs=[
            MetricScoreConfig(
                metric_id="a.missing",
                axis_id="a",
                direction="higher_better",
                min_value=0.0,
                max_value=10.0,
            ),
        ],
        axis_score_configs=[AxisScoreConfig(axis_id="a", display_name="A", weight=1.0)],
    )
    axis_scores = compute_axis_scores([], scoring_config)

    assert axis_scores[0].available is False
    assert axis_scores[0].score is None


def test_compute_total_score() -> None:
    """测试总分只使用可用维度。"""
    scoring_config = ScoringConfig(
        metric_score_configs=[
            MetricScoreConfig(
                metric_id="a.good",
                axis_id="a",
                direction="higher_better",
                min_value=0.0,
                max_value=10.0,
            ),
        ],
        axis_score_configs=[AxisScoreConfig(axis_id="a", display_name="A", weight=1.0)],
    )
    axis_scores = compute_axis_scores(
        [RawMetric(metric_id="a.good", axis_id="a", value=8.0, available=True)],
        scoring_config,
    )

    assert compute_total_score(axis_scores, scoring_config) == pytest.approx(80.0)


def test_compute_total_score_raises_without_available_axis() -> None:
    """测试没有可用维度时总分报错。"""
    scoring_config = ScoringConfig(
        axis_score_configs=[AxisScoreConfig(axis_id="a", display_name="A", weight=1.0)],
    )
    axis_scores = compute_axis_scores([], scoring_config)

    with pytest.raises(ScoringError):
        compute_total_score(axis_scores, scoring_config)
