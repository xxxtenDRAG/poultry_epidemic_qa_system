# 鹅养殖疫病风险评估交互式问答系统

面向中小鹅场的「疫病风险助手 + 全链路溯源」系统：养殖户每天巡栏记一笔，技术员随时问诊，批次从孵化到销售全程留痕。

<p align="center">
  <img src="frontend/src/assets/goose-mascot.png" alt="小鹅助手" width="170" />
</p>

基于 **RAG + LangGraph 多智能体 + 知识图谱 + 全链路溯源 + SSE 流式问答** 构建，同一套内核既可做养殖场日常工具，也可切换为比赛演示形态。

> 技术方案详见《鹅养殖疫病风险评估交互式问答系统——详细实施方案》。
>
> 全链路溯源：按批次记录并展示「孵化 → 育雏 → 生长 → 防疫 → 出栏 → 屠宰 → 质检 → 冷链 → 销售」九环节，支持追溯事件登记与链路完整度评估。

## 适用对象

| 角色 | 每天用它做什么 |
|------|----------------|
| 中小鹅场养殖户 | 手机打开 `/m` 记死淘、采食、温湿度；有异常直接问「小鹅」 |
| 场长 / 合作社 | 看批次存栏、今日待巡栏批次、风险等级与链路完整度 |
| 技术员 / 基层兽医 | 查疫病鉴别、免疫用药、消毒隔离规范，核对追溯证据 |
| 消费者 / 采购方 | 只读查看追溯码与批次链路（扫码页后续开放） |

> **产品路线**：先把「养殖场每天能用」做扎实（当前阶段），比赛展示时复用同一套内核，只换展示外壳与演示数据，不另起系统。

## 核心能力

- **疫病问答**：RAG + 知识图谱双通道检索 + 评估循环，SSE 流式输出，答案保留来源与免责声明；疑似急性疫情强制提示隔离、上报与联系官方兽医。
- **批次管理**：批次建档（养殖场、品种、鹅舍、孵化/入栏日期、数量、风险等级），支持编辑与状态流转。
- **日常巡栏**：死亡、淘汰、采食、饮水、温湿度、异常表现与处置措施；死淘自动扣减存栏，首页提示「今日已巡栏 / 待记录」。
- **全链路溯源**：九环节链路、追溯事件时间线、追溯码与链路完整度，支持电脑端与手机端登记。
- **手机端入口**：`/m` 四 Tab（巡栏 / 问诊 / 溯源 / 历史），面向养殖现场单手操作。首页为巡栏看板（完成度、存栏、死淘、风险提醒、批次筛选），批次详情含近 7 次死淘趋势、成活率、九环节和巡栏时间线；支持一键正常巡栏、拍照问诊、来源折叠、追溯码复制与事件登记，与桌面端共用同一套接口与数据。

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
│   ├── api/                # 接口路由（/chat /documents /graph /traceability）
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
| 阶段 2 | 数据工程与后端底座（检索评估+重排、Query 改写、异常处理） | ✅ 完成 |
| 阶段 3 | 核心业务集成 & 前后端联调（知识图谱、评估循环、图谱可视化） | ✅ 完成 |
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

### 阶段 3 里程碑验收清单

| 里程碑 | 内容 | 状态 |
|--------|------|------|
| M1 | 知识图谱构建（`scripts/build_graph.py`：LLM 抽三元组 → NetworkX → Louvain → `data/knowledge_graph.json`，7 块 → 39 节点/32 边/9 社区） | ✅ 验证通过 |
| M2 | 图谱检索融合（`knowledge_graph/retriever.py`：实体抽取 → 子图召回，与向量检索双通道；空图/未命中自动降级） | ✅ 验证通过 |
| M3 | 评估循环（relevance/sufficiency 打分，≤3 次重检索，`EVAL_LOOP_ENABLED` 开关可关；已验证开/关两态） | ✅ 验证通过 |
| M4 | 前端图谱页 ECharts 渲染 + `/api/graph/query`、`/api/graph/overview` 真实实现 + 文档更新 | ✅ 验证通过 |

### 知识图谱重建

新增/删除知识库文档后，重建图谱：

```bash
cd backend
python -m scripts.build_graph
```

## 团队硬性约定

1. 绝不先做高级功能——基础 RAG 跑通后再叠加 Agent 循环、知识图谱。
2. 复杂模块调不通允许关闭（降级开关），保证主体系统可用。
3. API 密钥、数据库密码一律走环境变量，严禁硬编码、严禁提交 Git。
4. 接口文档先行——后端接口改动必须同步更新 `docs/api.md`。

## 页面入口

| 入口 | 地址 | 面向 |
|------|------|------|
| 桌面端 | `http://localhost:5173/` | 场长、技术员、文档与图谱管理 |
| 手机端 | `http://localhost:5173/m` | 养殖户现场巡栏、拍照问诊、链路查看与会话历史 |
| 全链路溯源 | `http://localhost:5173/trace` | 批次链路、追溯事件与完整性 |
