# 项目结构说明

> 本文档说明每个文件夹/文件的用途，以及"新代码应该放哪里"。
> 结构对应《详细实施方案》2.3 目录规范。

---

## 1. 总览

```
poultry_epidemic_qa_system/
├── backend/                # FastAPI 后端（Python）
├── frontend/               # Vue3 + Element Plus 前端
├── docs/                   # 各类设计/接口/部署文档
├── datasets/               # 鹅养殖知识库 + 问答测试集
├── docker/                 # 容器化部署文件
├── .env / .env.example     # 环境变量（密钥，严禁提交）
├── .gitignore              # Git 忽略规则
└── README.md               # 项目入口说明
```

---

## 2. 根目录文件

| 文件 | 作用 | 说明 |
|------|------|------|
| `README.md` | 项目入口文档 | 技术栈、目录结构、快速启动、阶段规划 |
| `.gitignore` | Git 忽略规则 | 忽略 `.env`、venv、node_modules、data 等 |
| `.env` | 本地环境变量 | 存 API Key/数据库密码，**严禁提交 Git** |
| `.env.example` | 环境变量模板 | 可提交 Git，新成员复制为 `.env` 后填真实密钥 |

---

## 3. backend/ —— FastAPI 后端

```
backend/
├── main.py              # 应用入口：创建 app、注册路由、CORS、健康检查
├── requirements.txt     # Python 依赖清单
├── api/                 # 接口路由层（只管 HTTP 收发）
├── agent/               # LangGraph 多智能体（阶段 1 起）
├── data_pipeline/       # 离线数据流水线（阶段 1 起）
├── knowledge_graph/     # NetworkX 知识图谱（阶段 3 起）
├── core/                # 配置、日志（全局基础设施）
├── db/                  # MySQL 模型与连接
├── utils/               # 通用工具函数
└── tests/               # pytest 单元测试
```

### 3.1 main.py —— 后端入口

FastAPI 应用唯一入口。职责：
- 创建 `FastAPI` 实例
- 挂载 CORS（允许前端 5173 端口调试）
- `include_router` 注册 api/ 下的所有路由
- 提供 `/api/health` 健康检查

> 启动命令：`uvicorn main:app --reload --port 8000`
> 一般不需要改动本文件，新增接口只需在 `api/` 下加文件并在 main.py 注册。

### 3.2 api/ —— 接口路由层

只做"接收请求 → 返回响应"，业务逻辑交给下层模块。

| 文件 | 接口 | 职责 |
|------|------|------|
| `chat.py` | `POST /api/chat/stream` | 对话（SSE 流式），阶段 1 为 mock，阶段 3 调 agent 工作流 |
| `documents.py` | `POST /api/documents/upload` | 文档上传，阶段 3 调 data_pipeline 入库 |
| `graph.py` | `GET /api/graph/query` | 图谱查询，阶段 3 调 knowledge_graph |

**放置规则**：一个业务领域一个文件（如 `users.py`、`sessions.py`），文件内用 `APIRouter` 定义路由，最后在 main.py 注册。

### 3.3 core/ —— 配置与全局基础设施

| 文件 | 作用 |
|------|------|
| `config.py` | 用 pydantic-settings 读 `.env`，集中管理所有配置（API Key、MySQL、检索参数） |
| `logging.py` | 统一日志格式，`get_logger(name)` 供各模块使用 |

**放置规则**：全局只此一份的配置、日志、通用中间件放这里。

### 3.4 agent/ —— LangGraph 多智能体（核心业务层）

| 文件 | 作用 |
|------|------|
| `state.py` | Agent 状态结构（query / 检索结果 / 答案 / 溯源 / 循环次数） |
| `graph.py`（未来） | LangGraph 状态图：Query理解 → 检索 → 评估 ⇄ 循环 → 生成 → 溯源 |

**放置规则**：5 个 Agent 的逻辑按职责拆文件（如 `query_agent.py`、`retrieval_agent.py`），编排逻辑集中在 `graph.py`。

### 3.5 data_pipeline/ —— 离线数据流水线

职责：`原始文档 → 解析 → 清洗 → 分块 → bge 向量化 → ChromaDB 入库`

建议拆分为：
- `parse.py`：PDF/DOCX 解析（pdfplumber / python-docx）
- `chunk.py`：文本分块（chunk_size=512, overlap=50）
- `embed.py`：sentence-transformers bge 向量化
- `store.py`：ChromaDB 写入与检索

**放置规则**：与"文档处理"相关的代码都放这里，供 api/documents.py 和 agent/检索 Agent 调用。

### 3.6 knowledge_graph/ —— 知识图谱（阶段 3 已实现）

| 文件 | 作用 |
|------|------|
| `retriever.py` | 加载 `data/knowledge_graph.json` → 实体抽取 → 一跳子图召回；`query_entity` 供前端、`retrieve_graph` 供 Agent 双通道 |

- 图谱构建脚本：`backend/scripts/build_graph.py`（LLM 抽三元组 → NetworkX → Louvain → 落盘）

### 3.7 db/ —— 数据库层

| 文件 | 作用 |
|------|------|
| `session.py` | SQLAlchemy 引擎与会话（连接 MySQL） |
| `models.py` | 表模型：`session`（会话）、`document`（文档元数据） |

**放置规则**：新增表 → 在 `models.py` 加一个类；新增 CRUD → 建议按表拆模块（如 `db/crud_sessions.py`）。

### 3.8 utils/ —— 通用工具

跨模块复用的函数（如文件类型判断、文本清洗），**与业务无关**。业务相关的放各自模块。

### 3.9 tests/ —— 单元测试

pytest 测试脚本，文件命名 `test_*.py`。运行：`python -m pytest`。

---

## 4. frontend/ —— Vue3 + Element Plus 前端

```
frontend/
├── index.html            # HTML 入口
├── package.json          # npm 依赖与脚本
├── vite.config.js        # 构建配置 + /api 代理到后端 8000
└── src/
    ├── main.js           # 前端入口：挂载 Vue + Element Plus + 路由
    ├── App.vue           # 整体布局：顶栏 + 左侧菜单 + 内容区
    ├── router/index.js   # 路由表（对话/文档/图谱/历史）
    ├── api/request.js    # axios 统一封装（SSE 流式单独用 fetch）
    ├── views/            # 页面级组件（每路由一个）
    │   ├── ChatView.vue      # 对话页
    │   ├── UploadView.vue    # 文档管理页
    │   ├── GraphView.vue     # 知识图谱页
    │   └── HistoryView.vue   # 会话历史页
    ├── components/       # 可复用组件（聊天气泡、上传表单等）
    └── styles/           # 全局样式
```

**放置规则**：
- 页面 → `views/`（对应一个路由）
- 复用组件（气泡、卡片、弹窗）→ `components/`
- 接口调用 → `api/`（按模块拆，如 `api/chat.js`）
- 每个页面只负责布局与交互，数据请求放 api/ 层

---

## 5. docs/ —— 项目文档

| 文件 | 内容 |
|------|------|
| `architecture.md` | 系统架构（分层 + 管线 + P0/P1/P2 范围） |
| `api.md` | 接口文档（改动接口必须同步更新） |
| `agent_design.md` | 5 个 Agent 角色与评估循环设计 |
| `range.md` | 功能范围裁剪（做/不做/降级开关） |
| `deployment.md` | Docker 部署方案 |
| `setup.md` | 开发环境搭建指南 |
| `project_structure.md` | 本文档 |
| `meeting_notes/` | 每周会议记录 |

---

## 6. datasets/ —— 数据

| 目录 | 内容 |
|------|------|
| `knowledge/` | 鹅养殖知识库原始文档（起步 3–5 份 PDF） |
| `test_qa/` | 问答测试集（起步 20–30 条，最终 50–100 条） |

---

## 7. docker/ —— 部署

| 文件 | 作用 |
|------|------|
| `Dockerfile` | 后端镜像构建（阶段 4 完善） |
| `docker-compose.yml` | 一键编排：backend + MySQL + Chroma + Redis |

---

## 8. 数据流速览

```
前端页面 (views/) ──axios/SSE──> api/ 路由
                                    │
                                    ▼
                         agent/ LangGraph 工作流
                                    │
                     ┌──────────────┴──────────────┐
                     ▼                              ▼
            data_pipeline/（向量检索）      knowledge_graph/（图谱检索）
                     │                              │
                     └──────────┬───────────────────┘
                                ▼
                         LLM 生成 (DeepSeek) → SSE 流式返回前端
```

---

## 9. "新代码放哪"速查表

| 我要做什么 | 放哪里 |
|------------|--------|
| 新增一个接口 | `backend/api/` 下对应文件 + `main.py` 注册 |
| 写文档解析/分块/向量化逻辑 | `backend/data_pipeline/` |
| 写 Agent 节点逻辑 | `backend/agent/` |
| 写图谱逻辑 | `backend/knowledge_graph/` |
| 新增数据库表 | `backend/db/models.py` |
| 写通用工具函数 | `backend/utils/` |
| 写单元测试 | `backend/tests/test_*.py` |
| 新增前端页面 | `frontend/src/views/` + `router/index.js` |
| 抽复用组件 | `frontend/src/components/` |
| 前端调接口 | `frontend/src/api/` 下封装 |
| 接口变更 | 同步更新 `docs/api.md` |
