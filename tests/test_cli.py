"""命令行评估入口测试。"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.run_eval_cli import main

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_run_eval_cli_writes_expected_outputs(tmp_path: Path, capsys) -> None:
    """测试 CLI 能写出完整评估文件并打印摘要。"""
    exit_code = main(
        [
            "--config",
            str(PROJECT_ROOT / "configs" / "lfm_default.json"),
            "--scoring-config",
            str(PROJECT_ROOT / "configs" / "scoring_default.json"),
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert exit_code == 0
    for filename in [
        "request.json",
        "raw_metrics.json",
        "axis_scores.json",
        "evaluation_result.json",
        "chart_data.json",
    ]:
        path = tmp_path / filename
        assert path.exists()
        json.loads(path.read_text(encoding="utf-8"))

    captured = capsys.readouterr()
    assert "波形名称: default_lfm" in captured.out
    assert "总分:" in captured.out
    assert f"输出目录: {tmp_path}" in captured.out

