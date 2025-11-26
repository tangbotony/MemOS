# 推理结果说明文档 (Inference Results Documentation)

**任务 ID**: progressive_20251123_223311  
**生成时间**: 2025-11-23  
**说明对象**: 业务方、产品经理、算法工程师

---

## 1. 📂 目录结构概览

本文件夹包含 MemOS 系统在渐进式学习（Progressive Learning）模式下的推理结果。每个家庭（Family ID，如 `T8030P1322100087`）都有一套完整的数据文件。

```text
progressive_20251123_223311/
├── analysis/                   # [⭐核心] 综合分析报告，包含最终指标和错误分析
│   └── *_final_analysis.json
├── *_full_results.json         # [📄详情] 包含每一条测试数据的完整Prompt、推理过程和结果
├── *_FULL_RUN_accuracy_progress.png  # [📈图表] 准确率随时间变化的趋势图
├── memories/                   # [🧠记忆] 运行结束时生成的记忆库快照
├── evaluations/                # [📊分阶段] 每个学习阶段的详细评估指标
├── family_logs/                # [⚙️日志] 系统运行日志（查错用）
└── preflight_checks/           # [🛫预检] 运行前的基准检查数据
```

---

## 2. 🚀 核心文件说明 (业务方必读)

如果您想快速了解模型表现、准确率以及主要错误原因，请优先查看以下文件：

### 2.1 综合分析报告 (`analysis/*_final_analysis.json`)
这是每个家庭最终的总结报告，包含了最关键的业务指标。

*   **`summary`**: 总体表现概览
    *   `total`: 测试样本总数
    *   `correct`: 预测正确的数量
    *   `accuracy`: **核心准确率** (例如 0.54 表示 54%)
    *   `wrong_role_only`: 大类（Role）判断错误的数量
    *   `wrong_sub_only`: 子类（Sub-role）判断错误的数量
*   **`deep_analysis`**: 深度洞察
    *   `automated_suggestions`: **自动改进建议**（例如："视觉特征过于依赖颜色..."）
    *   `visual_confusion_keywords`: 容易导致混淆的高频关键词
*   **`correct_samples` / `error_samples`**:
    *   提供了具体的正误案例，包含 `reasoning`（模型推理逻辑），方便理解模型为什么对或为什么错。

### 2.2 准确率趋势图 (`*_FULL_RUN_accuracy_progress.png`)
*   **用途**: 直观展示模型随着“记忆”增多，效果是否在变好。
*   **看点**: 曲线如果呈上升趋势，说明模型通过学习历史数据，识别能力在增强。

---

## 3. 📄 详细数据说明 (Case 分析/研发用)

如果您需要深入分析某个具体的 Bad Case，或者查看模型具体的推理逻辑，请查看以下文件：

### 3.1 完整推理记录 (`*_full_results.json`)
这是一个巨大的 JSON 文件，记录了运行过程中每一条数据的完整交互。

*   **`original_description`**: 原始的视频/图像描述文本。
*   **`predicted_role_type` / `sub_role_type`**: 模型的预测结果。
*   **`reasoning`**: **推理思维链**。这里记录了模型是如何根据已有记忆和当前现象推导出结论的（例如："因为看到了两名女性从屋里出来，且穿着家居服，推测是家庭成员..."）。
*   **`retrieved_memories`**: **检索到的记忆**。展示了模型在做决定时，参考了哪些历史记忆（Fact）或归纳出的规律（Pattern）。
*   **`prompt`**: 发送给大模型的完整提示词。

### 3.2 记忆库快照 (`memories/*_memories.json`)
*   展示了系统在运行结束时，为该家庭构建的“知识库”。
*   包含 `Factual Memory`（事实记忆）和 `Pattern Memory`（规律记忆）。

---

## 4. 常见问题 (FAQ)

*   **Q: 为什么准确率 (accuracy) 看起来不高？**
    *   A: 请检查 `analysis` 文件夹中的 `deep_analysis` 字段。常见原因包括：视觉描述不够区分度（如全是“穿黑衣服的人”）、或场景本身极难区分（如路人和访客行为极相似）。
*   **Q: 如何找到某个具体的错误案例？**
    *   A: 打开 `*_full_results.json`，搜索具体的 `video_path` 或时间戳，查看其 `predicted` 与预期是否一致。


