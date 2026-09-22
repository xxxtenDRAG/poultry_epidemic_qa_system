# 鹅养殖疫病风险评估交互式问答系统 — 新成员使用手册

> 目标：从拉取仓库到正常使用系统，按本文档顺序执行即可。详细背景见 [README](../../README.md)，配置说明见 [config_guide](config_guide.md)，目录说明见 [project_structure](project_structure.md)。

---

## 0. 环境要求（首次需自查）

| 软件 | 版本要求 | 用途 |
|------|---------|------|
| Git | 任意 | 拉取代码 |
| Python | **3.11**（3.12+ 暂可运行，不建议） | 后端 |
| Node.js | 18+ | 前端构建 |
| MySQL | 5.7+/8.x，需能建库 | 会话/文档/消息持久化 |
| Docker（可选） | 20+ | 替代本机 MySQL |

> 远程服务器上的 Redis（`REDIS_URL`）当前阶段未使用，只影响阶段 2 之后的功能，缺失不阻塞启动。

---

## 1. 拉取仓库

```powershell
git clone https://gitee.com/cai-yeten/poultry_epidemic_qa_system.git
cd poultry_epidemic_qa_system
```

## 2. 配置环境变量

```powershell
Copy-Item .env.example .env
```

用编辑器打开 `.env`，**必须换成你自己的值**（详见 [config_guide](config_guide.md)）：

| 配置项 | 必填 | 说明 |
|--------|------|------|
| `DEEPSEEK_API_KEY` | 🔴 必填 | 从 DeepSeek 开放平台申请，问答核心 |
| `MYSQL_PASSWORD` | 🔴 必填 | 你本机 MySQL 的密码（账号默认 root） |
| `REDIS_URL` | 🟡 可暂不填 | 团队远程 Redis，阶段 2 起使用 |
| `HF_ENDPOINT` | 🟡 看网络 | 国内下载向量模型用 `https://hf-mirror.com` |

> `.env` 含密钥，已被 git 忽略，**绝不要提交或发给别人**。`.env.example` 是模板，保持原样。

## 3. 准备 MySQL

确保本机 MySQL 已启动，账号有建库权限。系统**首次启动时会自动创建 `goose_qa` 库和三张表**，无需手动建表。

## 4. 启动后端

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1      # 提示符前出现 (venv) 表示成功
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

启动成功标志：日志出现 `Uvicorn running on http://127.0.0.1:8000`。

**验证**：浏览器打开 http://localhost:8000/docs 能看到 Swagger 接口文档。

> 首次启动会自动**后台预热 bge 向量模型**（约 2-5s），不影响启动，只保证首次提问不卡。

## 5. 启动前端（新开一个终端）

```powershell
cd frontend
npm install
npm run dev
```

**验证**：浏览器打开 http://localhost:5173 能看到系统首页。

> 前端通过 Vite 代理把 `/api` 转发到 8000 端口，无需额外配置。

## 6. 首次使用前的准备：导入知识库

> ⚠️ 首次使用必须先导入知识文档，否则系统检索不到任何资料，回答会提示"资料不足"。

保持后端 venv 激活，在 `backend` 目录执行：

```powershell
# 导入全部知识文档（datasets/knowledge 下的 txt/md/PDF）
python -m scripts.ingest ..\datasets\knowledge

# 单独导入一个文件
python -m scripts.ingest ..\datasets\knowledge\鸭瘟与鹅副伤寒防控.txt
```

验证检索是否生效：

```powershell
python -m scripts.search "小鹅瘟怎么防控" --top-k 3
```

看到返回带距离分数的知识块即成功。

## 7. 日常使用指南

浏览器打开 **http://localhost:5173**：

| 页面 | 功能 | 说明 |
|------|------|------|
| **对话** | 问答 | 左下「＋新会话」新建；输入问题回车，约 3 秒内开始流式输出；答案下方有**溯源标签**（点击可查看来源文档与块）；左侧可切换/删除会话 |
| **文档管理** | 上传知识 | 支持 TXT/MD/PDF，上传后自动完成「解析→分块→向量化→入库」；可查看已入库文档、删除 |
| **会话历史** | 记录回看 | 查看历史会话与消息内容，可删除 |
| **知识图谱** | 图谱检索 | 阶段 3 功能，当前为占位页，查询会提示无结果（属预期） |

> 新上传的文档**立即生效**，同一会话追问即可命中新内容。

## 8. 常用命令速查（均在 `backend` 目录、venv 激活下）

```powershell
python -m scripts.ingest <路径>     # 导入知识库（文件或目录）
python -m scripts.search "<问题>"    # 检索测试（不带 LLM）
python -m scripts.agent_chat "<问题>" # 终端问答（完整 Agent 流程）
python -m pytest                     # 运行后端测试
```

## 9. 数据存放位置（建议了解）

| 数据 | 位置 | 是否提交 Git |
|------|------|-------------|
| 会话/消息/文档记录 | MySQL `goose_qa` 库 | 否（在服务器） |
| 向量库 | `data/chroma/`（仓库根目录下） | ❌ 已忽略 |
| 用户上传的原始文件 | `datasets/uploads/` | ❌ 已忽略 |
| 示例知识文档 | `datasets/knowledge/` | ✅ 随仓库 |
| 测试问答样本 | `datasets/test_qa/qa_samples.json` | ✅ 随仓库 |

## 10. 常见问题排查

| 现象 | 原因与解决 |
|------|-----------|
| 后端启动报 `python-multipart` 错误 | 依赖没装全：`pip install -r requirements.txt` 重装，或单独 `pip install python-multipart` |
| 提问回答"资料不足" | 知识库没导入，执行第 6 节 ingest |
| 回答慢/很久不出字 | DeepSeek API 偶发慢，等几秒重试；或确保 `.env` 里 `DEEPSEEK_API_KEY` 有效 |
| 启动报数据库连接失败 | MySQL 未启动 / 密码错误，检查 `.env` 的 `MYSQL_PASSWORD`，确认第 3 节 |
| 模型下载很慢或失败 | 在 `.env` 加 `HF_ENDPOINT=https://hf-mirror.com` 后重启后端 |
| 前端页面空白/接口 404 | 确认后端已启动（8000），前端 `npm run dev` 无报错 |
| 改了后端代码不生效 | 确认用 `--reload` 启动（热重载）；若改 `.env` 需重启后端 |
| 端口被占用 | 换端口：后端 `--port 8001`，前端 `vite.config.js` 里同步代理目标 |
| 运行 ingest / 问答报 `OSError: [WinError 4551] 应用程序控制策略已阻止此文件`（末尾提示 torch\lib\shm.dll、torch_cpu.dll 等） | 本机开启了 Windows 11「智能应用控制」（Smart App Control），它拦截了未受信任的 torch 二进制（含 bge 向量化/精排），与项目代码无关。关闭路径：设置 → 隐私和安全性 → Windows 安全中心 → 应用和浏览器控制 → 智能应用控制 → 关闭（关闭后需重装系统才能再开启，介意者改用未启用该策略的机器或容器） |

## 11. 开发协作约定

- **分支**：新功能在 `feature/<名称>` 分支开发，完成后提 MR 合入 master，**不要直接在 master 提交**
- **提交信息**：中文描述，格式 `<type>: <说明>`（如 `feat:`、`fix:`、`docs:`）
- **密钥**：一律走 `.env`，`.env.example` 只放占位符
- **文档索引**：[architecture](architecture.md) 架构 | [api](api.md) 接口 | [agent_design](agent_design.md) Agent 设计 | [range](range.md) 范围与进度 | [setup](setup.md) 详细安装 | [config_guide](config_guide.md) 配置说明
