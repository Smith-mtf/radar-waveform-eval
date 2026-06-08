# 发布检查清单 V1.0

## 自动检查

- [ ] 运行 `uv run pytest`
- [ ] 运行 `uv run ruff check .`
- [ ] 运行 CLI 示例

```powershell
uv run python scripts/run_eval_cli.py --config configs/lfm_default.json --scoring-config configs/scoring_default.json --output-dir outputs
```

## 桌面软件检查

- [ ] 运行 `uv run python -m desktop_app.main`
- [ ] 加载默认 LFM 配置
- [ ] 运行评估
- [ ] 查看综合评分卡
- [ ] 查看六维雷达图
- [ ] 查看模糊函数图
- [ ] 查看频谱图
- [ ] 查看底层指标表
- [ ] 生成本地模板报告
- [ ] 导出完整评估 JSON
- [ ] 导出原始指标 CSV
- [ ] 导出评分 CSV
- [ ] 导出图表数据 JSON
- [ ] 导出 Markdown 报告
- [ ] 导出 HTML 报告
- [ ] 保存项目
- [ ] 打开项目
- [ ] 打开 `examples/lfm_example.rwep.json`
- [ ] 打开 `examples/phase_code_example.rwep.json`

## 已知限制记录

- [ ] 记录未实现的雷达模型
- [ ] 记录评分配置依赖性
- [ ] 确认示例项目不包含真实敏感装备参数
- [ ] 确认测试不调用外部 API

