# Agent 设计（agent_design）

> 阶段 0 初稿，阶段 1/2 随 LangGraph 实践细化。

## 角色分工（层级式协作）

| 智能体 | 角色定位 | 核心职责 |
|--------|----------|----------|
| Query 理解 Agent | 入口调度员（Orchestrator） | 意图识别、Query 改写（多 Query 召回）、参数提取 |
| 检索 Agent | 知识检索员 | 向量检索 + 图谱检索双通道召回 |
| 评估 Agent | 质量把关员 | 检索结果相关性评分，决定是否重试 |
| 生成 Agent | 答案撰写员 | 基于检索结果生成最终答案 |
| 溯源 Agent | 引用标注员 | 为答案添加知识来源引用 |

## 状态结构（AgentState）

见 `backend/agent/state.py`：query / rewritten_queries / retrieval_results / answer / sources / loop_count。

## 评估循环（Loop Engineering）

| 指标 | 阈值 |
|------|------|
| 检索相关性 | > 0.7 |
| 信息充分度 | > 60% |
| 答案置信度 | > 0.65 |
| 引用完整度 | > 80% |
| 循环次数 | ≤ 3 |

终止条件：三项达标 **OR** 循环次数 ≥ 3。

## 已实现（阶段 1：M2 最小工作流）✅

代码：`backend/agent/graph.py`，运行：`python -m scripts.agent_chat "问题"`

```
START → query_understand（原文直通，单路召回）
      → retrieve（bge 向量化 + ChromaDB 检索，多路去重）
      → generate（检索结果构造 Prompt → DeepSeek 生成）
      → trace_sources（标注 文档/块号/距离）
      → END
```

- 调用 DeepSeek：`openai` 客户端 + `base_url=https://api.deepseek.com`（OpenAI 兼容接口）
- 无评估循环、无 Query 改写、无图谱通道（阶段 2/3 补齐）

## TODO

- [x] ~~LangGraph StateGraph 最简样例（阶段 1）~~ → 已实现
- [ ] Query 改写 + 多 Query 召回（阶段 2）
- [ ] 接入图谱通道（阶段 3）
- [ ] 评估 Agent + 循环控制（阶段 3）
- [ ] 各 Agent 输入输出精确定义
