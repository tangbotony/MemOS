# MemOS Quality Pack Runner

这个适配器把 `quality-packs/datasets/memos/memos-golden-recall-v0` 读取成统一的
`EvaluationRun` 报告。当前只支持 `shadow` 和 `mock`，两种模式都**不调用模型、
不访问网络、不生成 recall accuracy**。它们只验证 manifest、文件 SHA-256、样本绑定、
样本覆盖和 fixture 引用完整性；因此结果会明确标记为 `result: not_available`。

```bash
python -m evaluation.quality_runner.memos_quality_runner \
  --quality-packs-root /path/to/quality-packs \
  --dataset-id memos-golden-recall-v0 \
  --mode shadow \
  --output /tmp/memos-evaluation-run.json
```

输出包括：

- `run`：产品、dataset/version、dataset content hash、目标 revision、Runner 版本和执行耗时；
- `items`：每条样本的 `status=not_available`、`fixtureMatch=pass`，以及空的 latency/token/cost 字段；
- `scorecard`：fixture 覆盖率和引用完整性，不伪装成模型质量分；
- `reportSha256`：对报告主体的 canonical JSON 计算的 SHA-256。

真实模型 Runner 接入时，应复用同一报告形状，填充逐样本 answer、latency、token、cost
和 Evidence 引用，并由可信服务端计算 recall 指标。不能把本适配器的
`fixtureMatchRate` 当作产品质量分数或准出证据。
