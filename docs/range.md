# 范围裁剪（range）

> 阶段 0 集体评审产出：明确做 / 不做，防止新人贪多。

## 进度

- 阶段 0/1 已完成（M1-M5 验收通过）：数据管线、LangGraph 最小图、MySQL 三表 + 接口、前端 4 页面、24 条测试样本。
- 阶段 2 已完成（M1-M4）：M1 检索评估 + bge-reranker 精排 ✅（Hit@1 66.7%→79.2%，见 `eval_report.md`）；M2 Query 改写多路召回 ✅；M3 统一异常处理 + 文档删除联动清理 ✅。剩余：真实 PDF 知识库扩充后复测。
- 阶段 3 已完成（M1-M4）：M1 知识图谱构建（`scripts/build_graph.py`，7 块示例 → 39 节点 / 32 边 / 9 社区）✅；M2 图谱检索融合（实体抽取 → 子图召回，空图/未命中自动降级）✅；M3 评估循环（relevance/sufficiency 打分 + ≤3 次重检索，`EVAL_LOOP_ENABLED` 开关，已验证开关开/关两态）✅；M4 前端图谱页 ECharts 渲染 + `/api/graph/query`、`/api/graph/overview` 真实实现 ✅。
- 知识库现状：3 份示例文档，共 7 块（`datasets/knowledge/`）。

## 做（P0 + P1）

1. 文档上传 → 解析 → 分块 → 向量化 → ChromaDB 入库
2. 向量 RAG 检索 + bge-reranker 精排
3. LangGraph 多智能体工作流（Query 理解 → 检索 → 生成 → 溯源），评估循环作为 P1
4. NetworkX 知识图谱 + Louvain 社区检测 + 图谱检索（P1）
5. SSE 流式问答 + Vue3 前端页面（对话 / 上传 / 图谱 / 历史）
6. MySQL 会话与文档元数据管理
7. Docker Compose 本地部署

## 不做（P2，仅文档）

- 登录账号、后台管理、动态知识库、完整监控、Neo4j 生产迁移

## 降级开关

- 评估循环调不通 → 配置关闭，保留基础问答
- 知识图谱调不通 → 关闭图谱通道，仅向量检索
