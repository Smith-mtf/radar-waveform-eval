# 相位编码波形生成代码提取

本文档仅用于审阅当前实现，不作为新的运行入口。代码来源如下：

- `radar_eval_core/waveforms.py`：波形生成入口、采样点计算、相位编码 IQ 生成。
- `radar_eval_core/schemas.py`：`phase_code` 配置合法性校验。

## 生成入口中的相位编码分支

```python
def generate_waveform(config: WaveformConfig) -> WaveformSignal:
    """根据严格定义的波形配置生成复基带 IQ 信号。"""
    total_samples = _calculate_total_samples(config.sample_rate_hz, config.pulse_width_s)
    t = np.arange(total_samples, dtype=np.float64) / config.sample_rate_hz
    amplitude = math.sqrt(config.peak_power_w)
    metadata = _base_metadata(config, total_samples)

    if config.waveform_type == "rect":
        iq = np.full(total_samples, amplitude + 0.0j, dtype=np.complex128)
    elif config.waveform_type == "lfm":
        iq, lfm_metadata = _generate_lfm(config, t, amplitude)
        metadata.update(lfm_metadata)
    elif config.waveform_type == "phase_code":
        iq, phase_code_metadata = _generate_phase_code(config, total_samples, amplitude)
        metadata.update(phase_code_metadata)
    else:
        raise ValueError(f"不支持的波形类型: {config.waveform_type}")

    iq = iq.astype(np.complex128, copy=False)
    if len(t) != len(iq):
        raise ValueError("时间轴和 IQ 序列长度不一致。")

    return WaveformSignal(
        t=t,
        iq=iq,
        sample_rate_hz=config.sample_rate_hz,
        metadata=metadata,
    )
```

## 采样点数计算

```python
_SAMPLE_COUNT_ATOL = 1e-9


def _calculate_total_samples(sample_rate_hz: float, pulse_width_s: float) -> int:
    """计算严格整数采样点数。"""
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz 必须大于 0。")
    if pulse_width_s <= 0:
        raise ValueError("pulse_width_s 必须大于 0。")

    raw_samples = sample_rate_hz * pulse_width_s
    rounded_samples = round(raw_samples)
    if not np.isclose(raw_samples, rounded_samples, rtol=0.0, atol=_SAMPLE_COUNT_ATOL):
        raise ValueError("sample_rate_hz * pulse_width_s 必须为整数采样点数。")

    total_samples = int(rounded_samples)
    if total_samples < 2:
        raise ValueError("total_samples 必须至少为 2。")

    return total_samples
```

## 相位编码 IQ 生成核心

```python
def _generate_phase_code(
    config: WaveformConfig,
    total_samples: int,
    amplitude: float,
) -> tuple[npt.NDArray[np.complex128], dict[str, Any]]:
    """生成二相相位编码复基带波形及其定义 metadata。"""
    code = _normalize_phase_code(config.phase_code)
    code_length = len(code)
    if total_samples % code_length != 0:
        raise ValueError("phase_code 波形要求 total_samples 能被 code_length 整除。")

    samples_per_chip = total_samples // code_length
    chip_duration_s = samples_per_chip / config.sample_rate_hz
    symbols = np.asarray(code, dtype=np.float64)
    iq = (amplitude * np.repeat(symbols, samples_per_chip)).astype(np.complex128)
    metadata = {
        "code_length": code_length,
        "samples_per_chip": samples_per_chip,
        "chip_duration_s": chip_duration_s,
    }
    return iq, metadata
```

## 相位码归一化

```python
def _normalize_phase_code(phase_code: list[int] | None) -> list[int]:
    """将 0/1 或 -1/1 相位码显式转换为 -1/1 符号。"""
    if phase_code is None:
        raise ValueError("phase_code 波形必须提供相位编码序列。")

    unique_values = set(phase_code)
    if unique_values == {0, 1}:
        return [-1 if value == 0 else 1 for value in phase_code]
    if unique_values == {-1, 1}:
        return list(phase_code)

    raise ValueError("phase_code 只允许使用完整的 0/1 或 -1/1 二相编码。")
```

## 配置校验

```python
class WaveformConfig(BaseModel):
    """波形基础配置。"""

    waveform_type: Literal["rect", "lfm", "phase_code"] = Field(
        default="lfm",
        description="波形类型",
    )
    name: str = Field(default="default_waveform", description="波形名称")
    carrier_frequency_hz: float = Field(default=10e9, gt=0, description="载频")
    bandwidth_hz: float = Field(default=20e6, gt=0, description="带宽")
    pulse_width_s: float = Field(default=20e-6, gt=0, description="脉宽")
    sample_rate_hz: float = Field(default=100e6, gt=0, description="采样率")
    peak_power_w: float = Field(default=1.0, gt=0, description="峰值功率")
    phase_code: list[int] | None = Field(default=None, description="二相相位编码序列")

    @model_validator(mode="after")
    def validate_phase_code_usage(self) -> Self:
        """校验相位编码配置与波形类型一致。"""
        if self.waveform_type != "phase_code":
            if self.phase_code is not None:
                raise ValueError("phase_code 仅允许用于 phase_code 波形。")
            return self

        if self.phase_code is None:
            raise ValueError("phase_code 波形必须提供相位编码序列。")
        if len(self.phase_code) < 2:
            raise ValueError("phase_code 长度必须至少为 2。")

        unique_values = set(self.phase_code)
        if unique_values not in ({0, 1}, {-1, 1}):
            raise ValueError("phase_code 只允许使用完整的 0/1 或 -1/1 二相编码。")

        return self
```

## 模糊函数图表数据生成

代码来源：`radar_eval_core/evaluation_pipeline.py`。

```python
AMBIGUITY_HEATMAP_DELAY_SPAN_SAMPLES = 256
AMBIGUITY_HEATMAP_DELAY_POINTS = 129
AMBIGUITY_HEATMAP_DOPPLER_POINTS = 81
```

```python
def _compute_ambiguity_heatmap_chart(request: EvaluationRequest, iq: np.ndarray) -> dict[str, Any]:
    """生成轻量二维模糊函数热力图数据。"""
    max_delay = iq.size - 1
    delay_span = min(max_delay, AMBIGUITY_HEATMAP_DELAY_SPAN_SAMPLES)
    delay_count = min(AMBIGUITY_HEATMAP_DELAY_POINTS, 2 * delay_span + 1)
    if delay_count % 2 == 0:
        delay_count -= 1
    delay_samples = np.unique(
        np.round(np.linspace(-delay_span, delay_span, delay_count)).astype(int),
    )
    if not np.any(delay_samples == 0):
        delay_samples = np.sort(
            np.unique(np.concatenate([delay_samples, np.array([0], dtype=int)])),
        )
    doppler_hz = np.linspace(
        -request.evaluation.doppler_max_hz,
        request.evaluation.doppler_max_hz,
        AMBIGUITY_HEATMAP_DOPPLER_POINTS,
    )
    result = compute_ambiguity_function(
        iq,
        sample_rate_hz=request.waveform.sample_rate_hz,
        doppler_hz=doppler_hz,
        delay_samples=delay_samples,
    )
    sample_rate_hz = float(request.waveform.sample_rate_hz)
    delay_samples_list = [int(value) for value in result.delay_samples]
    return {
        "delay_samples": delay_samples_list,
        "delay_us": [float(value / sample_rate_hz * 1e6) for value in result.delay_samples],
        "doppler_hz": [float(value) for value in result.doppler_hz],
        "magnitude_normalized": result.ambiguity_magnitude_normalized.tolist(),
        "matrix_shape": "doppler_by_delay",
        "downsampled": True,
        "sample_rate_hz": sample_rate_hz,
        "delay_window_samples": int(delay_span),
        "doppler_window_hz": float(request.evaluation.doppler_max_hz),
    }
```

该函数输出的 `magnitude_normalized` 矩阵形状为 `doppler_by_delay`，桌面端只消费这份 `chart_data`，不在 UI 层重新计算雷达指标。

## UI 侧取用模糊函数图表数据

代码来源：`desktop_app/windows/main_window.py`。

```python
def _update_charts(self, chart_data: dict[str, Any]) -> None:
    waveform = chart_data.get("waveform_preview")
    if isinstance(waveform, dict):
        y_values = waveform.get("real_amplitude", waveform.get("magnitude", []))
        preview_duration_s = waveform.get("preview_duration_s")
        x_range = (
            (0.0, float(preview_duration_s))
            if isinstance(preview_duration_s, int | float)
            else None
        )
        self.preview_chart.plot_curve(
            waveform.get("time_s", []),
            y_values,
            x_label="Time s",
            y_label="Amplitude (Real Part)",
            x_range=x_range,
            y_range=(-1.5, 1.5),
        )
    else:
        self.preview_chart.show_message("波形预览数据不可用")

    heatmap = chart_data.get("ambiguity_heatmap")
    if isinstance(heatmap, dict):
        x_values = heatmap.get("delay_us")
        x_label = "Delay us"
        if not x_values:
            x_values = heatmap.get("delay_samples", [])
            x_label = "Delay samples"
        self.ambiguity_chart.plot_ambiguity_surface(
            x_values,
            heatmap.get("doppler_hz", []),
            heatmap.get("magnitude_normalized", []),
            x_label=x_label,
        )
    else:
        self.ambiguity_chart.show_message("模糊函数图数据不可用")
```

## 3D 模糊函数绘制入口

代码来源：`desktop_app/windows/main_window.py` 的 `ChartPanel`。

```python
def plot_ambiguity_surface(
    self,
    x_values: list[float],
    y_values: list[float],
    matrix: list[list[float]],
    *,
    x_label: str = "Delay samples",
) -> None:
    """Render normalized ambiguity magnitude as a -60..0 dB 3D surface."""
    if pg is None or gl is None:
        self.show_message("当前环境不支持 pyqtgraph OpenGL 3D 模糊函数图")
        return

    x_axis = np.asarray(x_values, dtype=float)
    y_axis_hz = np.asarray(y_values, dtype=float)
    image = np.asarray(matrix, dtype=float)
    if (
        x_axis.ndim != 1
        or y_axis_hz.ndim != 1
        or x_axis.size == 0
        or y_axis_hz.size == 0
        or image.ndim != 2
        or image.shape != (y_axis_hz.size, x_axis.size)
    ):
        self.show_message("模糊函数 3D 图数据不可用")
        return

    try:
        image_db = _ambiguity_db_image(image)
    except ValueError:
        self.show_message("ambiguity surface peak is unavailable")
        return

    try:
        gl_widget = self._ensure_gl_widget()
    except Exception:
        self.show_message("当前 OpenGL 环境无法创建 3D 模糊函数图")
        return

    if self._plot_widget is not None:
        self._plot_widget.hide()
    gl_widget.show()
    self._clear_gl_items(gl_widget)

    y_axis, y_label = _scaled_doppler_axis(y_axis_hz)
    x_display = _normalized_surface_axis(x_axis)
    y_display = _normalized_surface_axis(y_axis)
    z_surface_db = image_db.T.astype(float, copy=False)
    z_display = (z_surface_db + 60.0) / 60.0
    surface = gl.GLSurfacePlotItem(
        x=x_display,
        y=y_display,
        z=z_display,
        colors=_ambiguity_surface_colors(z_surface_db),
        shader=None,
        smooth=False,
    )
    surface.setGLOptions("opaque")
    gl_widget.addItem(surface)

    grid = gl.GLGridItem()
    grid.setSize(2.0, 2.0, 1.0)
    grid.setSpacing(0.5, 0.5, 1.0)
    grid.translate(0.0, 0.0, 0.0)
    gl_widget.addItem(grid)

    axis = gl.GLAxisItem()
    axis.setSize(1.0, 1.0, 1.0)
    axis.translate(-1.0, -1.0, 0.0)
    gl_widget.addItem(axis)

    gl_widget.setCameraPosition(distance=4.0, elevation=34, azimuth=-45)
    self._caption_label.setText(
        "3D ambiguity surface: "
        f"{x_label} [{_compact_number(float(np.min(x_axis)))}, "
        f"{_compact_number(float(np.max(x_axis)))}], "
        f"{y_label} [{_compact_number(float(np.min(y_axis)))}, "
        f"{_compact_number(float(np.max(y_axis)))}], Z -60..0 dB",
    )
    self._caption_label.show()
```

## 模糊函数显示辅助函数

代码来源：`desktop_app/windows/main_window.py`。

```python
def _ambiguity_db_image(image: np.ndarray) -> np.ndarray:
    """将归一化线性幅度矩阵转换为用于显示的 -60 到 0 dB 矩阵。"""
    peak = float(np.max(image))
    if not math.isfinite(peak) or peak <= 0.0:
        raise ValueError("ambiguity heatmap peak must be positive.")
    safe_image = np.maximum(image, np.finfo(float).tiny)
    image_db = 20.0 * np.log10(safe_image / peak)
    return np.clip(image_db, -60.0, 0.0)


def _ambiguity_colormap_lut() -> np.ndarray:
    """返回模糊函数 dB 热力图使用的伪彩色查找表。"""
    if pg is not None:
        try:
            return pg.colormap.get("viridis").getLookupTable(nPts=256)
        except Exception:
            colors = np.array(
                [
                    [0, 0, 128],
                    [0, 128, 255],
                    [0, 220, 120],
                    [255, 230, 0],
                    [255, 0, 0],
                ],
                dtype=np.ubyte,
            )
            positions = np.linspace(0.0, 1.0, colors.shape[0])
            return pg.ColorMap(positions, colors).getLookupTable(nPts=256)
    return np.empty((0, 4), dtype=np.ubyte)


def _ambiguity_surface_colors(image_db: np.ndarray) -> np.ndarray:
    """Map a -60..0 dB ambiguity surface to flattened OpenGL vertex colors."""
    lut = _ambiguity_colormap_lut()
    if lut.size == 0:
        return np.ones((*image_db.shape, 4), dtype=float)
    if lut.shape[1] == 3:
        alpha = np.full((lut.shape[0], 1), 255, dtype=lut.dtype)
        lut = np.hstack([lut, alpha])
    color_index = np.clip(((image_db + 60.0) / 60.0 * 255.0).astype(int), 0, 255)
    return (lut[color_index].astype(float) / 255.0).reshape(-1, 4)


def _scaled_doppler_axis(doppler_hz: np.ndarray) -> tuple[np.ndarray, str]:
    """Return a display-scaled Doppler axis while preserving chart_data values."""
    max_abs = float(np.max(np.abs(doppler_hz))) if doppler_hz.size else 0.0
    if max_abs >= 1e6:
        return doppler_hz / 1e6, "Doppler MHz"
    if max_abs >= 1e3:
        return doppler_hz / 1e3, "Doppler kHz"
    return doppler_hz, "Doppler Hz"


def _normalized_surface_axis(values: np.ndarray) -> np.ndarray:
    """Normalize a physical axis to [-1, 1] for readable 3D OpenGL display."""
    if values.size == 0:
        return values.astype(float, copy=True)
    span = float(np.ptp(values))
    if span <= 0.0:
        return np.zeros_like(values, dtype=float)
    center = float(np.min(values) + span / 2.0)
    return (values.astype(float, copy=False) - center) / (span / 2.0)
```
