# API 接口文档

> 后端接口改动必须同步更新本文档。Swagger 地址：`http://localhost:8000/docs`

## 1. 健康检查

- `GET /api/health` → `{ "status": "ok", "project": ..., "version": ... }`

## 2. 对话（SSE 流式）✅ 已接入 LangGraph

- `POST /api/chat/stream`
  - 请求体：`{ "session_id": 可选(int), "question": "问题" }`，`session_id` 为空自动创建新会话
  - 响应：`text/event-stream`，事件格式 `data: {json}\n\n`
    - 增量：`{ "type": "token", "content": "字" }`
    - 结束：`{ "type": "done", "answer": "完整答案", "sources": [{ "doc", "index", "distance" }] }`
  - 副作用：用户问题与助手答案（含溯源 JSON）自动写入 `message` 表

## 3. 会话管理 ✅

- `POST /api/sessions` — 创建，请求体 `{ "title": 可选 }` → `{ "id", "title", "created_at" }`
- `GET /api/sessions` — 列表（最近更新在前）
- `GET /api/sessions/{id}` — 详情（含 `messages`，按时间正序）
- `DELETE /api/sessions/{id}` — 删除（消息级联删除）

## 4. 文档管理 ✅ 上传已接真实流水线

- `POST /api/documents/upload`（multipart/form-data，字段 `file`，支持 .pdf/.docx/.txt/.md）
  - 流程：保存文件 → 解析 → 分块 → bge 向量化 → ChromaDB 入库 → 元数据写 MySQL
  - 返回：`{ "id", "filename", "file_type", "chunk_count", "status", "created_at" }`
- `GET /api/documents` — 文档列表（最新在前）
- `DELETE /api/documents/{id}` — 删除文档：MySQL 元数据 + ChromaDB 向量块 + 本地文件

## 5. 知识图谱 ✅ 已接入真实图谱检索（阶段 3）

- `GET /api/graph/query?entity=xxx` → `{ "entity", "nodes": [{ "id", "type", "community" }], "edges": [{ "source", "target", "relation" }] }`
  - 返回实体一跳子图；图谱文件缺失或未命中实体时 nodes/edges 为空（不报错）
- `GET /api/graph/overview` → `{ "node_count", "edge_count", "community_count", "communities": [{ "id", "size" }] }`
  - 图谱规模与社区统计（前端图谱页概览用）

## 6. 对话链路说明（阶段 3）

- 检索为双通道：向量召回（多 Query + bge-reranker 精排） + 知识图谱子图（实体命中时）
- 图谱通道空 / 未命中实体 → 自动跳过，不影响主链路
- 评估循环（`run()` 非流式链路）：生成后对 `relevance` / `sufficiency`（0-5）打分，
  任一 < 3 且循环次数 < `EVAL_MAX_LOOPS` 时改写 Query 重检索；`EVAL_LOOP_ENABLED=false`
  时跳过评估直接出答案（降级）。SSE 流式链路（`prepare`→`stream_generate`）不做循环。

## 7. TODO

- [ ] 流式对话的中途取消 / 断流重连（阶段 3）
