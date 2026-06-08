"""模糊函数图表组件。"""

from __future__ import annotations

from typing import Any

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtWidgets import QVBoxLayout, QWidget


class AmbiguityWidget(QWidget):
    """从 chart_data 展示模糊函数相关图表。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化模糊函数图表。"""
        super().__init__(parent)
        self._figure = Figure(figsize=(5, 3), facecolor="#ffffff")
        self._canvas = FigureCanvas(self._figure)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)
        self.set_chart_data({})

    def set_chart_data(self, chart_data: dict[str, Any]) -> None:
        """显示 chart_data 中的 ambiguity 数据。"""
        self._figure.clear()
        axis = self._figure.add_subplot(111)
        axis.set_facecolor("#ffffff")
        heatmap = chart_data.get("ambiguity_heatmap")
        required_keys = {"delay_samples", "doppler_hz", "magnitude_normalized"}
        if isinstance(heatmap, dict) and required_keys <= set(heatmap):
            delay_samples = np.asarray(heatmap["delay_samples"], dtype=float)
            doppler_hz = np.asarray(heatmap["doppler_hz"], dtype=float)
            magnitude = np.asarray(heatmap["magnitude_normalized"], dtype=float)
            if (
                delay_samples.size > 0
                and doppler_hz.size > 0
                and magnitude.ndim == 2
                and magnitude.shape == (doppler_hz.size, delay_samples.size)
            ):
                image = axis.imshow(
                    magnitude,
                    aspect="auto",
                    origin="lower",
                    interpolation="nearest",
                    extent=[
                        float(delay_samples.min()),
                        float(delay_samples.max()),
                        float(doppler_hz.min()),
                        float(doppler_hz.max()),
                    ],
                )
                axis.set_xlabel("delay samples")
                axis.set_ylabel("Doppler Hz")
                axis.set_title("normalized ambiguity magnitude")
                self._figure.colorbar(image, ax=axis)
            else:
                self._draw_unavailable(axis)
        elif "zero_delay_doppler_cut" in chart_data:
            cut = chart_data["zero_delay_doppler_cut"]
            axis.plot(cut.get("doppler_hz", []), cut.get("magnitude_normalized", []))
            axis.set_xlabel("Doppler Hz")
            axis.set_ylabel("normalized magnitude")
            axis.set_title("zero-delay Doppler cut")
        else:
            self._draw_unavailable(axis)
        self._figure.tight_layout()
        self._canvas.draw_idle()

    @staticmethod
    def _draw_unavailable(axis: Any) -> None:
        """显示图表数据不可用提示。"""
        axis.text(
            0.5,
            0.5,
            "Chart data unavailable",
            ha="center",
            va="center",
            transform=axis.transAxes,
        )
        axis.set_axis_off()
