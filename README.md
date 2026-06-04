# 雷达波形性能评估桌面软件 V1.0

本项目用于建设一个基于 Python + PySide6 / QtWidgets 的桌面软件，面向雷达波形的探测性能、抗干扰性能和反侦察性能评估。V1.0 阶段先建立工程结构、数据模型、占位算法接口和最小桌面入口，不实现复杂雷达算法和完整桌面界面。

## 技术栈

- Python 3.12+
- PySide6 / QtWidgets：桌面界面
- NumPy / SciPy：雷达信号处理基础能力
- Matplotlib：第一版图表
- Pydantic：配置与评估结果数据结构
- pytest：自动化测试
- ruff：代码检查
- mypy：类型检查
- PyInstaller：后续桌面打包预留

## 本地安装

推荐使用 `uv` 管理环境和依赖：

```powershell
uv sync
```

如果只需要执行单条命令，也可以直接使用：

```powershell
uv run python -m desktop_app.main
```

## 运行测试

```powershell
uv run pytest
uv run ruff check .
```

## 启动桌面程序

```powershell
uv run python -m desktop_app.main
```

启动后会显示最小主窗口，标题为“雷达波形性能评估软件 V1.0”，窗口大小为 1200x800。

## 后续开发路线

1. 完善 `radar_eval_core` 的波形配置、场景配置和评估结果模型。
2. 按指标类别逐步实现探测性能、抗干扰性能和反侦察性能的可测试算法。
3. 在 `desktop_app` 中补充页面切换、参数表单、图表展示和结果对比。
4. 增加项目文件读写、评估任务后台执行和报告导出。
5. 补充 PyInstaller 打包脚本和桌面发布流程。

