# 阶段 3 设计：核心业务集成 & 前后端联调

> 对应《详细实施方案》阶段 3（B1 知识图谱 / B2 评估循环 / F2 图谱可视化）。
> B3（SSE/上传/会话）与 F1 已在阶段 1-2 完成，本阶段不做重复。

## 目标

端到端跑通"图谱增强 RAG + 质量评估循环"，前端能可视化实体关系。

## 里程碑拆分

| 里程碑 | 内容 | 对应方案 | 产出 |
|--------|------|---------|------|
| **M1 知识图谱构建** | LLM 抽三元组 → NetworkX 构图 → Louvain 社区检测 | B1 | `scripts/build_graph.py` + `data/knowledge_graph.json` |
| **M2 图谱检索融合** | 实体抽取 → 图谱子图召回 → 与向量检索融合（GraphRAG） | B1 | `knowledge_graph/retriever.py`，agent 双通道 |
| **M3 评估循环** | 相关性+充分度打分 → 不达标改写重检索（≤3 次），可降级 | B2 | agent 循环节点 + `EVAL_LOOP_ENABLED` 开关 |
| **M4 前端图谱页 + 检查点** | `/api/graph/query` 真实实现 + ECharts 渲染 + 文档更新 | F2 + B1 | GraphView 真实图谱 + 验证 |

## M1 知识图谱构建

### 本体设计（实体 / 关系）

| 实体类型 | 示例 |
|---------|------|
| 疾病 disease | 小鹅瘟、鸭瘟、鹅副黏病毒病、禽流感 |
| 病原 pathogen | 鹅细小病毒、沙门氏菌、鸭瘟病毒 |
| 症状 symptom | 灰白稀粪、头颈肿胀、神经症状 |
| 药物 drug | 恩诺沙星、氟苯尼考、高免血清 |
| 疫苗 vaccine | 小鹅瘟弱毒疫苗、鸭瘟弱毒疫苗 |
| 宿主 host | 雏鹅、种鹅、成年鸭 |
| 传播途径 route | 消化道、垂直传播、水污染 |
| 防控 measure | 消毒、隔离、全进全出 |

| 关系 | 语义 |
|------|------|
| 引起 (pathogen→disease) | 病原导致疾病 |
| 表现为 (disease→symptom) | 疾病出现症状 |
| 预防 (vaccine→disease / measure→disease) | 疫苗/措施预防疾病 |
| 治疗 (drug→disease) | 药物治疗疾病 |
| 易感 (host→disease) | 宿主对疾病易感 |
| 传播 (disease→route) | 疾病的传播途径 |

### 三元组抽取（DeepSeek）

- 输入：每个知识块（≤512 字）
- Prompt：指定实体/关系类型，输出 JSON 数组 `[{"head","rel","tail"}]`
- **质量约束**：每块最多抽 5 条；JSON 解析失败跳过该块并记日志（不阻塞流水线）
- 抽取结果按 (head, rel, tail) 去重合并

### 构图与社区检测

- `networkx.DiGraph`；节点带 `type`、`doc` 属性
- `python-louvain`（`community.best_partition`）做社区检测，社区号写回节点属性
- 持久化：`data/knowledge_graph.json`（nodes + edges 两个数组），Neo4j 生产预留
- 脚本：`python -m scripts.build_graph`（读 ChromaDB 全部块 → 抽三元组 → 构图 → 保存）

## M2 图谱检索融合（GraphRAG）

1. **实体抽取**：LLM 从用户 query 抽 1-3 个候选实体（JSON，失败降级为分词词表匹配）
2. **图谱召回**：命中实体 → 取一跳邻居（节点 + 关系边），组装成子图文本
3. **融合**：`retrieve` 节点改为双通道 —— 向量召回 Top-K + 图谱子图，合并去重后作为 LLM 上下文
4. 图谱为空或未命中时**自动跳过图谱通道**（降级，不影响主链路）

## M3 评估循环（可降级）

- 生成答案后，评估 Agent 打分：`relevance`（检索相关性 0-5）+ `sufficiency`（信息充分度 0-5）
- 判定：任一 < 3 → 改写 query（复用阶段 2 的 rewrite_queries）→ 重检索 → 重新生成
- **循环上限 3 次**，LangGraph 条件边判断（`loop_count < 3 and not pass`）
- 降级开关：`.env` 加 `EVAL_LOOP_ENABLED`（默认 `true`），为 `false` 时跳过评估直接出答案
- AgentState 增加 `eval_result`、`pass` 字段

## M4 前端图谱页

- 依赖：新增 `echarts`（关系图 `type: 'graph'`）
- `GraphView.vue`：输入实体 → `GET /api/graph/query?entity=xxx` → 渲染实体节点 + 关系边；显示社区配色
- 接口：
  - `GET /api/graph/query?entity=xxx` → `{ entity, nodes, edges }`（真实实现）
  - `GET /api/graph/overview` → 节点/边/社区统计（可选）
- 图谱页无结果时提示"知识库未命中实体"（不报错）

## 检查点验收

1. `build_graph` 跑通：7 块示例知识 → 三元组、图谱、社区数可统计
2. 提问含图谱实体时，答案上下文含图谱子图（日志可查）
3. 评估循环：故意问模糊问题，验证 ≤3 次内重检索收敛；关闭开关后跳过
4. 前端图谱页可渲染实体关系
5. 更新 `docs/architecture.md`、`api.md`、`range.md`

## 风险与降级（项目硬性约定）

| 风险 | 降级方案 |
|------|---------|
| 三元组抽取质量差/不稳定 | 每块限 5 条、解析失败跳过、不追求 100% 准确 |
| 评估循环不稳定/拖慢回答 | `EVAL_LOOP_ENABLED=false` 关闭，注释保留逻辑 |
| 示例知识库小、图谱稀疏 | 图谱通道自动降级；真实 PDF 扩充后效果增强 |
| 前后端字段不一致 | 图谱接口返回结构在 api.md 先行定死 |
