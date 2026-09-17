# 系统架构设计

> 阶段 0 产出初稿，随开发迭代更新。参照《详细实施方案》1.2 / 1.3。

## 1. 分层架构

```
前端层（Vue3 + Element Plus）：对话界面(SSE流式) / 文档管理(上传预览) / 知识图谱(可视化)
        │  HTTP / SSE
API 层（FastAPI）：/api/chat/stream  /api/documents  /api/graph
        │
智能体层（LangGraph）：Query理解Agent → 检索Agent → 评估Agent ⇄ 循环控制 → 生成Agent → 溯源Agent
        │
知识层（双通道召回）：
        向量通道（ChromaDB：文档分块向量 + 相似度检索 + bge-reranker 精排）
        图谱通道（NetworkX：实体-关系三元组 + Louvain 社区检测 + 多跳推理）
        │
数据层：MySQL(用户/会话) + ChromaDB(向量持久化) + Redis(缓存)
```

## 2. 核心管线

- **离线管线**：原始文档 → 解析 → 清洗 → 分块 → 向量化 → 入库 ChromaDB
- **图谱管线（阶段 3）**：ChromaDB 全部块 → DeepSeek 抽三元组（每块 ≤5 条，解析失败跳过）→ NetworkX 构图 → Louvain 社区检测 → `data/knowledge_graph.json`（`python -m scripts.build_graph`）
- **在线管线**：User Query → Query 理解（改写多路）→ 向量检索 → Reranker ⟂ 知识图谱子图召回（实体命中时）→ 融合构造 Prompt → LLM 生成 → 评估循环（相关性/充分度，≤3 次，可关闭）→ SSE 流式返回

## 3. 功能范围（P0 / P1 / P2）

| 等级 | 功能 | 状态 |
|------|------|------|
| P0 必做 | 文档上传解析分块入库；向量 RAG 检索；SSE 流式问答；会话管理；基础前端页面；Docker 本地部署 | 阶段 1-3 完成（Docker 阶段 4） |
| P1 选做 | Agent 评估重试循环；NetworkX 知识图谱；图谱可视化（ECharts） | 阶段 3 完成 |
| P2 仅文档 | 登录账号、后台管理、动态知识库、完整监控、Neo4j 迁移 | 不编码 |

## 4. TODO（评审补充项）

- [ ] 补 ER 图（session / document 表）
- [ ] 标注 SSE 断流、超时处理方案
