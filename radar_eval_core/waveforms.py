"""波形生成相关占位接口。"""

from __future__ import annotations

from .schemas import WaveformConfig


def build_waveform(config: WaveformConfig) -> None:
    """根据波形配置生成采样序列的占位函数。"""
    _ = config
    # TODO: 实现 LFM、相位编码、频率捷变等波形生成。
    raise NotImplementedError("波形生成算法将在后续版本实现。")

