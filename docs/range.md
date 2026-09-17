# 范围裁剪（range）

> 阶段 0 集体评审产出：明确做 / 不做，防止新人贪多。

## 进度

- 阶段 0/1 已完成（M1-M5 验收通过）：数据管线、LangGraph 最小图、MySQL 三表 + 接口、前端 4 页面、24 条测试样本。
- 知识库现状：3 份文档（`datasets/knowledge/`，共 8 块），后续补充真实 PDF 后执行 `python -m scripts.ingest`。

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
