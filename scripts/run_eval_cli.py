"""命令行算法评估入口。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main(argv: list[str] | None = None) -> int:
    """读取配置、运行完整算法评估并写出 JSON 文件。"""
    from radar_eval_core.evaluation_pipeline import compute_waveform_evaluation
    from radar_eval_core.schemas import (
        EvaluationRequest,
        ScenarioEnvironmentConfig,
        apply_scenario_environment_config,
    )
    from radar_eval_core.scoring import ScoringConfig

    parser = argparse.ArgumentParser(description="运行雷达波形算法核心评估。")
    parser.add_argument("--config", default="configs/lfm_default.json", help="评估请求配置 JSON")
    parser.add_argument(
        "--scoring-config",
        default="configs/scoring_default.json",
        help="评分配置 JSON",
    )
    parser.add_argument(
        "--scenario-config",
        default="configs/scenario_default.json",
        help="场景与环境配置 JSON；会覆盖 --config 中的 scenario/jammer/evaluation",
    )
    parser.add_argument("--output-dir", default="outputs", help="评估输出目录")
    args = parser.parse_args(argv)

    request = EvaluationRequest.model_validate(_read_json(Path(args.config)))
    scenario_environment = ScenarioEnvironmentConfig.model_validate(
        _read_json(Path(args.scenario_config)),
    )
    request = apply_scenario_environment_config(request, scenario_environment)
    scoring_config = ScoringConfig.model_validate(_read_json(Path(args.scoring_config)))
    result = compute_waveform_evaluation(request, scoring_config)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "request.json", request.model_dump(mode="json"))
    _write_json(
        output_dir / "raw_metrics.json",
        [metric.model_dump(mode="json") for metric in result.raw_metrics],
    )
    _write_json(
        output_dir / "axis_scores.json",
        [axis.model_dump(mode="json") for axis in result.axis_scores],
    )
    _write_json(output_dir / "evaluation_result.json", result.model_dump(mode="json"))
    _write_json(output_dir / "chart_data.json", result.chart_data)

    print(f"波形名称: {request.waveform.name}")
    for axis in result.axis_scores:
        if axis.available and axis.score is not None:
            print(f"{axis.axis_id}: {axis.score:.2f}")
        else:
            print(f"{axis.axis_id}: unavailable ({axis.reason})")
    print(f"总分: {result.overall_score:.2f}")
    print(f"输出目录: {output_dir}")
    return 0


def _read_json(path: Path) -> Any:
    """读取 JSON 文件。"""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, data: Any) -> None:
    """写出 UTF-8 JSON 文件。"""
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
