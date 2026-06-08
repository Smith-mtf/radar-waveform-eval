"""频谱图组件。"""

from __future__ import annotations

from typing import Any

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtWidgets import QVBoxLayout, QWidget


class SpectrumWidget(QWidget):
    """从 chart_data 展示频率-PSD 曲线。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化频谱图组件。"""
        super().__init__(parent)
        self._figure = Figure(figsize=(5, 3), facecolor="#ffffff")
        self._canvas = FigureCanvas(self._figure)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)
        self.set_chart_data({})

    def set_chart_data(self, chart_data: dict[str, Any]) -> None:
        """显示 chart_data 中的 spectrum_psd。"""
        self._figure.clear()
        axis = self._figure.add_subplot(111)
        axis.set_facecolor("#ffffff")
        spectrum = chart_data.get("spectrum_psd")
        if isinstance(spectrum, dict) and "frequency_hz" in spectrum and "psd_w_per_hz" in spectrum:
            frequency_hz = spectrum["frequency_hz"]
            psd = spectrum["psd_w_per_hz"]
            if len(frequency_hz) == len(psd) and frequency_hz:
                scale = 1e6 if max(abs(value) for value in frequency_hz) >= 1e6 else 1.0
                x_values = [value / scale for value in frequency_hz]
                axis.plot(x_values, psd, color="#0f766e", linewidth=1.4)
                axis.set_xlabel("frequency MHz" if scale == 1e6 else "frequency Hz")
                axis.set_ylabel("PSD W/Hz")
                axis.grid(color="#d7dee6", linewidth=0.8)
            else:
                self._draw_unavailable(axis)
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

