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

- `POST /api/sessions` — 创建，请求体 `{ "title": 可选 }` → 会话对象（见下）
- `GET /api/sessions?keyword=&topic=` — 列表（最近活动在前）
  - `keyword` 匹配会话标题或消息内容；`topic` 为提问维度 id（见下表）
  - 每项字段：`{ id, title, created_at, last_active_at, message_count, question_count, first_question, topics }`
- `GET /api/sessions/overview` — 概览
  - `{ session_count, message_count, question_count, dimension_count, latest_at, dimensions: [{ id, label, count, questions }] }`
  - `dimensions[].questions` 为该维度的快捷提问模板（对话页按维度提问用）
- `GET /api/sessions/{id}` — 详情（含 `messages`，按时间正序）
- `DELETE /api/sessions/{id}` — 删除（消息级联删除）
- `POST /api/sessions/delete` — 批量删除，请求体 `{ "ids": [1, 2] }`

### 提问维度（topics）

维度由 `backend/core/topics.py` 的关键词规则识别，**不落库**，随会话内容实时重算；
新增维度只需在 `TOPICS` 里加一项，历史页与对话页会自动出现对应标签与提问卡片。

| id | 维度 |
|----|------|
| `diagnosis` | 疫病诊断与鉴别 |
| `vaccine` | 免疫与疫苗 |
| `biosecurity` | 消毒与生物安全 |
| `medication` | 用药与兽药规范 |
| `husbandry` | 饲养管理与孵化 |
| `nutrition` | 营养代谢与中毒 |
| `emergency` | 疫情处置与法规 |
| `risk` | 风险评估与分级 |
| `general` | 综合问答（未命中任何维度时的兜底） |

## 4. 文档管理 ✅ 上传 / 列表 / 预览 / 检索 / 本地语料补录

- `POST /api/documents/upload`（multipart/form-data，字段 `file`，支持 .pdf/.docx/.txt/.md）
  - 流程：保存文件 → 解析 → 分块 → bge 向量化 → ChromaDB 入库 → 元数据写 MySQL
  - 返回：`{ "id", "filename", "doc_key", "source", "file_type", "chunk_count", "indexed_chunks", "status", "created_at", "replaced" }`
  - 同名文件按「替换」处理（`replaced=true`）：先清旧向量与旧记录，再写新的
- `GET /api/documents` — 文档列表（最新在前）
  - MySQL 元数据与向量库实际块数合并；离线入库、没有 MySQL 记录的语料也会列出（此时 `id=null`）
  - `source`：`upload`（datasets/uploads）/ `knowledge`（datasets/knowledge）/ `unknown`
- `GET /api/documents/stats` — 知识库概览
  - `{ "document_count", "registered_count", "vector_count", "pending_count", "latest_at", "upload_dir", "knowledge_dir" }`
- `GET /api/documents/chunks?name=xxx&offset=0&limit=20&keyword=` — 分块预览
  - `origin=vector` 读向量库；`file` 表示尚未入库、回退到本地文件现场分块；`missing` 表示找不到内容
- `POST /api/documents/search` — 知识库语义检索
  - 请求体：`{ "query": "问题", "top_k": 5, "rerank": true }`
  - 返回：`{ "query", "count", "hits": [{ "doc", "index", "text", "chars", "rerank_score", "distance" }] }`
- `DELETE /api/documents/{id}` — 按 id 删除：MySQL 元数据 + ChromaDB 向量块 + 本地文件
- `POST /api/documents/delete` — 批量删除，请求体 `{ "ids": [1, 2], "names": ["鹅病诊断与策略防治.txt"] }`
  - `names` 用于离线入库、没有 MySQL 记录的文档
- `GET /api/documents/library` — 本地知识库清单
  - `{ "dir", "items": [{ "filename", "size", "modified_at", "indexed_chunks", "status" }] }`，`status` 为 `indexed` / `missing`
- `GET /api/documents/topics` — 知识库的提问维度覆盖度
  - `[{ "id", "label", "chunk_count", "doc_count", "docs", "questions", "thin" }]`
  - `thin=true` 表示该维度知识块少于 10，属于储备短板，前端会提示补充语料
  - 每块只计入得分最高的维度，`questions` 为该维度快捷提问模板
- `POST /api/documents/library/sync` — 把 `datasets/knowledge/` 语料补录入库并登记 MySQL
  - 请求体 `{ "names": [], "force": false }`，`names` 为空表示全部；块数与库中一致时默认跳过重新向量化
  - 返回：`[{ "filename", "action": "created/updated/skipped/failed", "chunk_count", "message" }]`

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
