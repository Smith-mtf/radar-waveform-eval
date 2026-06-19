"""桌面评估服务测试。"""

from __future__ import annotations

import json
from pathlib import Path

from desktop_app.services.evaluation_service import EvaluationService
from radar_eval_core.schemas import EvaluationRequest, WaveformConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_default_waveform_configs_only_contain_waveform() -> None:
    """测试默认波形配置文件不再混入场景与环境配置。"""
    for filename in ["lfm_default.json", "phase_code_default.json"]:
        data = json.loads((PROJECT_ROOT / "configs" / filename).read_text(encoding="utf-8"))
        assert set(data) == {"waveform"}


def test_load_scenario_environment_config() -> None:
    """测试可单独加载场景与环境配置。"""
    service = EvaluationService()
    config = service.load_scenario_environment_config(
        PROJECT_ROOT / "configs" / "scenario_default.json",
    )

    assert config.scenario.name == "default_scenario"
    assert config.jammer.enabled is True
    assert config.jammer.jammer_type == "noise"
    assert config.evaluation.pfa == 1e-6
    assert config.evaluation.num_pulses == 64


def test_apply_scenario_environment_preserves_waveform() -> None:
    """测试应用场景与环境配置时保留原波形配置。"""
    service = EvaluationService()
    request = EvaluationRequest(
        waveform=WaveformConfig(
            name="keep_this_waveform",
            waveform_type="lfm",
            bandwidth_hz=7e6,
            pulse_width_s=8e-6,
            sample_rate_hz=40e6,
        ),
    )
    config = service.load_scenario_environment_config(
        PROJECT_ROOT / "configs" / "scenario_default.json",
    )

    merged = service.apply_scenario_environment_config(request, config)

    assert merged.waveform.name == "keep_this_waveform"
    assert merged.waveform.bandwidth_hz == 7e6
    assert merged.scenario.target_range_m == 50_000.0
    assert merged.jammer.enabled is True
    assert merged.evaluation.prf_hz == 1000.0
