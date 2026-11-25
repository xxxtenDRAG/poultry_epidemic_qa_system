# 鹅养殖疫病风险评估交互式问答系统｜GitHub 协作规则

> 版本：v1.0（2026-11-25）
> 状态：生效
> 适用仓库：https://github.com/xxxtenDRAG/poultry_epidemic_qa_system
> 团队：项目组成员（当前提交记录中的主要维护者：倪佳音、蔡业腾）
> 目标：多人并行开发时，`master` 始终可启动、可演示；每个功能都能追溯到 Issue、分支和 PR。

## 0. 一页版核心规则

1. **禁止直接 push `master`。**
2. 每个人从最新 `master` 创建自己的任务分支；同一时间只保留一条活跃任务分支。
3. 一个 Issue 对应一条分支和一个 PR；分支名必须包含开工日期 `YYYYMMDD`。
4. 没有实际提交时不得开 PR；禁止创建占位 PR、空 PR 和“先开 PR 再补代码”。
5. 所有 PR 至少 1 人 Review；接口、SSE、数据库、密钥相关改动至少 2 人 Review。
6. 使用 Squash merge 合并，合并后删除任务分支。
7. 不提交 `.env`、API Key、数据库密码、日志、向量库、上传文件和 `node_modules`。
8. 接口变更必须同步 `docs/api.md` 和前端调用；数据库变更必须说明迁移与回滚。
9. 合并前必须通过前端构建和后端最小测试；不允许“本地能跑就行”。
10. 可演示、可提交的稳定版本在 `master` 上打版本标签。

## 1. 分支模型

| 分支 | 用途 | 谁能合并 | 规则 |
|---|---|---|---|
| `master` | 可启动、可演示的稳定版本 | 由 PR 合并 | 禁止直接 push；只接收经过 Review 的 PR；合并后打 tag |
| `feat/YYYYMMDD-...` | 新功能 | 任务负责人 | 从最新 `master` 创建，只合并到 `master` |
| `fix/YYYYMMDD-...` | 修 Bug | 任务负责人 | 从最新 `master` 创建；冻结期只允许 P0 修复 |
| `docs/YYYYMMDD-...` | 文档、规则、Issue/PR 模板 | 任务负责人 | 不改业务代码 |
| `chore/YYYYMMDD-...` | 配置、依赖、CI、脚本 | 任务负责人 | 需要另一名维护者 Review |

说明：

- 本仓库当前以 `master` 为主干；如后续需要“预发布/联调”分支，再增设 `dev`，规则同样适用：`dev` 只能通过 PR 合入，发布时再由 `dev` 向 `master` 提 PR。
- 仓库中已有的历史功能分支只作为存档，不代表任务分配。开始新任务时从最新 `master` 新建分支。
- 如果 GitHub 套餐不支持分支保护，也按本规则手工执行，任何人不得用管理员权限绕过。

## 2. 每次写代码的标准流程

### 2.1 开始前：先有 Issue，再从最新 master 建分支

建分支前确认：

- [ ] GitHub 上已有对应 Issue，并明确由自己负责。
- [ ] 一个 Issue 只对应一个任务；预计 2 天完不成时先拆分 Issue。
- [ ] 自己当前没有另一条未完成的任务分支。
- [ ] 工作区干净，没有把旧改动带进新分支。

标准步骤（本仓库同时存在 `origin`=Gitee、`github`=GitHub 两个远程，以下以 GitHub 为例）：

```text
git fetch github
git switch master
git pull --ff-only github master
git status --short
git switch -c feat/YYYYMMDD-模块-任务-姓名
git branch --show-current
```

含义：

1. `git fetch github`：获取 GitHub 最新分支信息。
2. `git switch master`：回到主干。
3. `git pull --ff-only github master`：只做快进合并，不能基于几天前的代码开工。
4. `git status --short`：必须没有输出；有输出说明工作区不干净，先处理。
5. `git switch -c ...`：按第 3 节命名规则创建自己的任务分支。
6. `git branch --show-current`：确认分支名与计划一致。

### 2.2 开发中：小步提交

```text
git add 指定文件
git commit -m 'feat(chat): 支持多轮上下文追问'
```

规则：

- 只 `git add` 自己改的文件，不执行无脑 `git add .`。
- 一次提交只做一件事，提交信息能看懂。
- 每天至少提交并推送一次自己的任务分支。
- 不提交 `.env`、密钥、数据库文件、日志、`node_modules`、`dist`、向量库和上传文件。
- 分支超过 1 天未同步时，合并前必须重新同步 `master`。

### 2.3 提交前：同步并自测

```text
git fetch github
git merge github/master
```

默认使用 merge 同步，不要求新手使用 rebase。若使用 rebase，只允许在自己的任务分支上做，并提前告知 Reviewer。

提交前检查：

- [ ] 已同步最新 `master`，没有冲突残留。
- [ ] 前端 `npm run build` 通过。
- [ ] 后端相关 `pytest` 或最小 smoke test 通过。
- [ ] 本地 `GET /api/health` 返回 200。
- [ ] 没有提交密钥、`.env`、日志、向量库和大文件。
- [ ] 没有覆盖别人模块的代码。
- [ ] 接口变更已更新 `docs/api.md` 和前端调用。
- [ ] 页面有加载、成功、空、错误状态。

### 2.4 开 PR：目标必须是 master

```text
git push -u github feat/YYYYMMDD-模块-任务-姓名
```

然后在 GitHub 开 PR，`base` 选 `master`。

开 PR 前确认：

- 分支上已经有实际文件差异；没有提交或没有文件改动时，不开 PR。
- GitHub 显示 `There isn’t anything to compare` 或 `0 changed files` 时，立即停止。
- 页面顶部确认 `base: master`、`compare: 自己的任务分支`。
- PR 标题、关联 Issue、改动内容、验收方式和证据必须能对应真实内容。

PR 必须填写：

- 目标与背景；
- 关联 Issue，例如 `Closes #12`；
- 改了什么；
- 如何验收；
- 截图、录屏或 curl；
- 是否修改接口、SSE、数据库；
- 风险和回滚方式；
- 自查清单。

## 3. 分支与提交命名

### 3.1 分支命名

统一格式：

```text
类型/YYYYMMDD-模块-任务-姓名
```

示例：

```text
feat/20261125-chat-multiturn-nijiayin
feat/20261125-graph-api-caiyeten
feat/20261125-doc-ingest-caiyeten
fix/20261125-sse-reconnect-nijiayin
docs/20261125-collaboration-rules
chore/20261125-ci-build-nijiayin
```

规则：

- `YYYYMMDD` 使用北京时间、分支创建当天。
- 日期表示开工日期，不表示截止日期；分支跨天继续开发时不改名。
- 分支超过 2 天仍未合并，必须拆分或说明原因。
- 全小写，单词用短横线连接；不使用空格、中文、下划线或连续短横线。
- 分支名尽量控制在 60 个字符以内。
- 分支合并后立即删除远程分支。

### 3.2 Commit 规范

格式：

```text
类型(范围): 简短说明
```

| 类型 | 用途 |
|---|---|
| `feat` | 新功能 |
| `fix` | 修复 Bug |
| `docs` | 文档 |
| `test` | 测试 |
| `refactor` | 重构，不改变行为 |
| `chore` | 配置、依赖、CI、脚本 |
| `style` | 格式调整，不改变逻辑 |

示例：

```text
feat(chat): 支持多轮上下文追问
fix(api): 修复 SSE 断线后重复消息
docs(api): 同步文档管理接口说明
test(qa): 补充 10 条图谱检索样例
chore(ci): 增加前端构建检查
```

不允许：

- `update`
- `fix bug`
- `111`
- `最终版`
- `再改一下`

## 4. Pull Request 规范

### 4.1 PR 标题

```text
[模块] 简短说明
```

示例：

```text
[Chat] 支持多轮上下文与追问指代消解
[Graph] 增加节点详情与模糊搜索
[API] 修复文档删除后残留向量
[Docs] 补充协作规则与启动说明
```

### 4.2 PR 模板

```text
## 目标

## 关联 Issue
Closes #

## 改动内容

## 如何验收

## 截图 / 录屏 / curl

## 接口、SSE 或数据库变更

## 风险与回滚

## 自查
- [ ] 已同步最新 master
- [ ] 前端 build 通过
- [ ] 后端测试或 smoke test 通过
- [ ] 没有提交密钥、.env、日志和大文件
- [ ] 页面有加载、成功、空、错误状态
- [ ] 接口变更已同步 docs/api.md 和前端调用
```

### 4.3 PR 规则

- PR 目标分支必须是 `master`，发布 PR 除外。
- 没有实际提交或页面显示没有差异时，不得创建 PR；占位 PR、空 PR 一律关闭。
- 一个 PR 只解决一个 Issue；不要把三个功能塞进一个 PR。
- PR 超过 400 行必须拆分，除非是自动生成文件、数据文件或数据库迁移。
- 没有验收方式的 PR 不合并。
- 前端 PR 必须有截图；后端 PR 必须有 curl 或测试；数据/知识库 PR 必须有来源说明。
- 合并后删除任务分支，不在仓库堆积已合并分支。

## 5. Review 与合并

### 5.1 Review 配对

- 默认交叉 Review：作者之外的另一名维护者 Review。
- 高风险 PR 需要 2 人 Review；只有两人时，两人都必须确认。
- 不允许作者自己批准自己的 PR。
- Reviewer 24 小时内必须响应；超过 24 小时在站会提出。
- 评论未解决前不合并。

高风险改动包括：

- 修改 `docs/api.md`、SSE 事件结构、请求/响应字段；
- 修改 `backend/db/` 下的模型、建表逻辑或迁移；
- 修改 `.env.example`、`backend/core/config.py`、模型/密钥配置；
- 修改 `backend/agent/` 的 LangGraph 流程、Prompt、评估循环；
- 修改 `backend/knowledge_graph/` 的构图、检索或缓存；
- 修改 `docker/`、部署脚本、启动方式；
- 修改文件上传、文档解析、权限或安全相关逻辑。

### 5.2 Reviewer 检查清单

- [ ] 是否满足 Issue 验收标准。
- [ ] 是否只改了自己的模块。
- [ ] 是否覆盖加载、成功、空、错误状态。
- [ ] 是否引入密钥、隐私数据或不必要的大文件。
- [ ] 是否破坏接口契约或数据库迁移。
- [ ] 是否有测试、curl、截图或录屏。
- [ ] 是否存在明显的安全、性能或可维护性问题。

### 5.3 合并方式

- 使用 **Squash and merge**，一个 PR 对应一个清晰提交。
- 合并前确认 Review 通过、没有冲突、构建/测试通过。
- 合并后删除远程任务分支。
- 禁止对 `master` 使用 force push。

## 6. 模块边界与共享文件

| 模块 | 主要路径 | 说明 |
|---|---|---|
| 前端对话 | `frontend/src/views/ChatView.vue` | 聊天、多轮上下文、图片识别、导出 |
| 前端文档 | `frontend/src/views/UploadView.vue` | 文档上传、知识库管理 |
| 前端历史 | `frontend/src/views/HistoryView.vue` | 会话历史、筛选、批量删除 |
| 前端图谱 | `frontend/src/views/GraphView.vue` | 知识图谱浏览与查询 |
| 前端公共 | `frontend/src/components/`、`router/`、`api/` | 公共组件、路由、请求封装 |
| 后端接口 | `backend/api/`、`backend/main.py` | REST、SSE、上传接口 |
| Agent | `backend/agent/`、`backend/core/llm.py` | LangGraph 工作流、Prompt、模型调用 |
| 数据管线 | `backend/data_pipeline/`、`backend/scripts/ingest.py` | 解析、分块、向量化、入库 |
| 知识图谱 | `backend/knowledge_graph/`、`backend/scripts/build_graph.py` | 构图、检索、缓存 |
| 数据库 | `backend/db/` | 模型、建表、会话与消息持久化 |
| 文档 | `README.md`、`docs/` | 使用手册、接口、架构、协作规则 |
| 部署 | `docker/`、`docker-compose.yml` | 容器化与部署 |

共享文件（修改前先在 Issue/PR 中说明，避免冲突）：

- `README.md`
- `docs/api.md`
- `backend/core/config.py`
- `.env.example`
- `frontend/package.json`、`frontend/package-lock.json`
- `backend/requirements.txt`
- `docker/docker-compose.yml`

修改共享文件时：

- 不做全文件格式化，只改必要行。
- 不同时改多个共享文件，除非是同一个接口变更。
- 冲突时由最近修改该文件的负责人主导解决，另一方复核。

## 7. 接口、SSE 与数据库规则

### 7.1 接口

- 新增/修改接口必须同步更新 `docs/api.md`。
- 请求/响应字段变更必须同步前端调用，不能在 PR 里只改后端。
- 删除字段或改语义属于破坏性变更，必须在 PR 中标注“破坏性变更”并说明兼容方案。
- 错误响应保持统一结构，不返回堆栈或密钥信息。

### 7.2 SSE

- 事件类型、字段名、结束标志变更必须前后端同时改。
- 断线重连、重复消息、异常中断必须有处理。
- SSE 相关 PR 必须附 curl 或日志证据。

### 7.3 数据库

- 表结构变更必须提供建表/迁移脚本，并说明回滚方式。
- 不得删除生产数据；本地调试数据不得提交。
- 会话、消息、文档表的关键字段变更需要两人 Review。
- 数据库密码只从环境变量读取，禁止硬编码。

## 8. 密钥、数据与大文件

- `.env` 已被 `.gitignore` 排除，**永远不要提交**。
- `.env.example` 只放占位符，不放真实 Key。
- 不在代码、文档、截图、日志中粘贴真实 API Key、数据库密码或 Token。
- `datasets/` 只提交有授权、可公开的知识文档，并保留来源说明。
- 不提交 `data/` 下的向量库、运行缓存、上传文件、日志；`data/graph_extract_cache.json` 按现有约定可提交。
- 单文件超过 10MB 的二进制资源使用 Git LFS 或外部存储，并在 PR 中说明。
- 发现密钥泄露时：立即在平台吊销/轮换，清理提交历史，并通知所有协作者。

## 9. 本地检查

后端（在 `backend` 目录）：

```text
.\.venv\Scripts\python.exe -m pytest
```

最小 smoke test：

```text
Invoke-WebRequest http://127.0.0.1:8000/api/health
```

前端（在 `frontend` 目录）：

```text
npm run build
```

提交前至少完成与改动相关的检查；涉及前后端联调的 PR 必须同时启动两边验证。

## 10. 发布、回滚与冻结

- 可演示版本在 `master` 上打 tag：`v主版本.次版本.修订号`，例如 `v1.0.0`。
- 发布前确认：前端构建通过、后端可启动、知识库可检索、核心问答链路可用。
- 回滚优先使用 `git revert` 或 GitHub 的 Revert PR，禁止 force push `master`。
- 发生线上/演示事故时，先在 Issue 记录现象、影响范围、回滚版本和后续修复。
- 比赛/答辩前 48 小时进入冻结期，只允许 `fix/` 分支修 P0 问题；冻结与解冻由主要维护者确认。

## 11. 每日同步与冲突处理

- 每个工作时段开始前先 `git fetch` + `git pull --ff-only`。
- 合并前先同步 `master`，解决冲突后再推送到自己的任务分支。
- 冲突处理原则：保留双方意图，不整文件覆盖；无法判断时找另一方确认。
- 不使用 `git push --force` 覆盖别人的远程分支。
- 不删除别人的未合并分支；确需清理时先在 Issue 中说明。

## 12. 附：新成员第一次提交检查表

- [ ] 已阅读本文件、`README.md` 和 `docs/user_guide.md`。
- [ ] 已配置 `.env`，但没有提交 `.env`。
- [ ] 已能从最新 `master` 创建任务分支。
- [ ] 已完成一次真实提交并推送。
- [ ] 已按模板开 PR，并写清验收方式。
- [ ] 已请另一名维护者 Review。
- [ ] 合并后已删除任务分支。