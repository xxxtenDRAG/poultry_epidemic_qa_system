# 鹅养殖疫病风险评估交互式问答系统

基于 **RAG + LangGraph 多智能体 + 知识图谱 + SSE 流式问答** 的鹅养殖疫病风险评估交互式问答系统。

> 技术方案详见《鹅养殖疫病风险评估交互式问答系统——详细实施方案》。

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| LLM 推理 | DeepSeek Chat（api.deepseek.com） |
| Embedding / Reranker | 本地 `BAAI/bge-small-zh-v1.5` / `bge-reranker-base`（sentence-transformers） |
| 向量存储 | ChromaDB（本地持久化） |
| 知识图谱 | NetworkX + Louvain 社区检测（生产预留 Neo4j） |
| Agent 框架 | LangGraph |
| 后端 | FastAPI + Python 3.11 |
| 数据库 | MySQL |
| 前端 | Vue 3 + Element Plus |
| 通信 | SSE 流式 |
| 部署 | Docker + Docker Compose |

## 目录结构

```
poultry_epidemic_qa_system/
├── backend/                # FastAPI 后端
│   ├── api/                # 接口路由（/chat /documents /graph）
│   ├── agent/              # LangGraph 智能体逻辑
│   ├── data_pipeline/      # 文档解析、分块、向量化入库
│   ├── knowledge_graph/    # NetworkX 知识图谱
│   ├── core/               # 配置、环境变量、日志
│   ├── db/                 # MySQL 模型与操作
│   ├── utils/              # 工具函数
│   ├── tests/              # 测试脚本
│   └── main.py             # FastAPI 入口
├── frontend/               # Vue3 + Element Plus
├── docs/                   # 架构 / 接口 / 部署 / 会议记录
├── datasets/               # 鹅养殖知识库 + 测试集
├── docker/                 # Dockerfile + docker-compose.yml
└── README.md
```

> 各目录/文件的详细用途与"新代码放哪"规范，见 [docs/project_structure.md](docs/project_structure.md)。

## 快速启动（开发环境）

> **新成员请先阅读完整使用手册：[docs/user_guide.md](docs/user_guide.md)**（拉取仓库 → 配置 → 启动 → 导入知识库 → 使用 → 排查）

### 后端

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env   # 只需填入 DeepSeek API Key（向量化走本地 bge，无需额外 Key）
uvicorn main:app --reload --port 8000
# Swagger 文档: http://localhost:8000/docs
```

### 前端

```bash
cd frontend
npm install
npm run dev
# 默认访问: http://localhost:5173（/api 已代理到后端 8000）
```

## 阶段规划

| 阶段 | 主题 | 状态 |
|------|------|------|
| 阶段 0 | 项目启动与环境统一（目录搭建、依赖跑通、设计文档初稿） | ✅ 完成 |
| 阶段 1 | 技术预研 & 独立模块 Demo（M1 数据管线 / M2 Agent / M3 数据库接口 / M4 前端 / M5 检查点） | ✅ 完成 |
| 阶段 2 | 数据工程与后端底座（检索评估+重排、Query 改写、异常处理） | 进行中（M1-M3 完成） |
| 阶段 3 | 核心业务集成 & 前后端联调（SSE 对接、知识图谱、评估循环） | 未开始 |
| 阶段 4 | 系统测试、容器化部署 | 未开始 |
| 阶段 5 | 文档整理、演示打磨 | 未开始 |

### 阶段 1 里程碑验收清单

| 里程碑 | 内容 | 状态 |
|--------|------|------|
| M1 | PDF/txt 解析 → 分块 → bge 向量化 → ChromaDB 入库与检索 | ✅ 验证通过 |
| M2 | LangGraph 工作流（理解→检索→生成→溯源），DeepSeek 问答 | ✅ 验证通过 |
| M3 | MySQL 三表 + 会话 CRUD + SSE 接口 + 文档上传流水线 | ✅ 验证通过 |
| M4 | 前端 4 页面对接真实接口（打字机流式、上传、历史、图谱） | ✅ 验证通过 |
| M5 | 知识库 3 份文档 / 24 条测试样本 / 文档收尾 | ✅ 验证通过 |

## 团队硬性约定

1. 绝不先做高级功能——基础 RAG 跑通后再叠加 Agent 循环、知识图谱。
2. 复杂模块调不通允许关闭（降级开关），保证主体系统可用。
3. API 密钥、数据库密码一律走环境变量，严禁硬编码、严禁提交 Git。
4. 接口文档先行——后端接口改动必须同步更新 `docs/api.md`。
