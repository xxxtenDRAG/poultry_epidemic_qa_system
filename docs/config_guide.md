# 新人配置指南（克隆项目后必读）

> 多人协同开发时，**每个成员的 .env 都是自己的**，不随 Git 提交。
> 仓库里只保留 `.env.example` 模板；克隆后第一步：复制模板 → 按本表填写 → 开始开发。

```powershell
# 项目根目录下执行
Copy-Item .env.example .env
```

---

## 1. 配置总原则

| 文件 | 是否提交 Git | 说明 |
|------|--------------|------|
| `.env.example` | ✅ 提交 | 公共模板，只放占位符，**不填真实密钥** |
| `.env` | ❌ 不提交（.gitignore 已忽略） | 每个人的本地配置，填自己的真实值 |

后端启动时自动从**项目根目录**的 `.env` 读取（[config.py](../backend/core/config.py) 已固定绝对路径，从任意目录启动都能读到，无需担心）。

---

## 2. 配置清单（哪些要换成你自己的）

### 🔴 必改 —— 必须换成你自己的

| 配置项 | 含义 | 在哪申请 | 说明 |
|--------|------|----------|------|
| `DEEPSEEK_API_KEY` | DeepSeek 对话模型 Key | platform.deepseek.com | **一人一个**，别用别人的；不填 M2 起所有功能用不了 |
| `MYSQL_PASSWORD` | 本机 MySQL 密码 | 自己安装 MySQL 时设置 | 连不上数据库 90% 是这里不对 |
| `REDIS_URL` | Redis 连接串 | 自己的 Redis 环境 | 格式见下方"常见坑" |

### 🟡 按自己环境改 —— 默认值不一定适用

| 配置项 | 默认值 | 什么时候要改 |
|--------|--------|--------------|
| `MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_USER` | localhost / 3306 / root | MySQL 不在本机或账号不同时 |
| `HF_ENDPOINT` | https://hf-mirror.com | 境外网络可留空；大陆建议保留（加速 bge 模型下载） |

### 🟢 团队统一 —— 不要个人改动

| 配置项 | 说明 |
|--------|------|
| `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` | 全队统一用官方地址与模型 |
| `EMBEDDING_MODEL` / `RERANK_MODEL` | bge 模型，统一才能保证向量库兼容 |
| `MYSQL_DATABASE` | 统一库名 `goose_qa` |
| `CHROMA_PERSIST_DIR` | 向量库路径，统一 `../data/chroma` |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` / `TOP_K` | 检索参数，阶段 2 由 B1 统一调优 |

---

## 3. 各开发阶段需要的配置

| 阶段 | 必须配置项 | 没有会怎样 |
|------|-----------|-----------|
| M1 数据管线（已完成） | 无 | bge 走本地，无需任何 Key |
| M2 Agent Demo | `DEEPSEEK_API_KEY` | 问答生成失败 |
| M3 数据库 + 接口 | `MYSQL_*`、`REDIS_URL` | 建表/会话保存失败 |
| 阶段 4 Docker 部署 | 全部 | docker-compose 会注入 `.env` |

---

## 4. 验证配置是否正确

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -c "from core.config import settings; print('DeepSeek Key 已配置:', bool(settings.DEEPSEEK_API_KEY)); print('MySQL 密码:', settings.MYSQL_PASSWORD); print('Redis:', settings.REDIS_URL)"
```

> ⚠️ 不要直接打印完整 API Key / 密码，防止截图泄密。

期望输出（示例）：

```
DeepSeek Key 已配置: True
MySQL 密码: 123456
Redis: redis://:xxxx@192.168.100.128:6379/0
```

---

## 5. 常见坑（老成员踩过的）

| 坑 | 说明 |
|----|------|
| 改了 .env 不生效 | 必须**重启服务**，`uvicorn --reload` 不会监听 .env 变化 |
| REDIS_URL 格式写错 | 带密码格式：`redis://:密码@主机:端口/库号`；密码含 `@ : /` 等特殊字符需 URL 编码 |
| .env 被覆盖 | IDE 打开 .env 时磁盘可能已被他人修改，保存前先确认（建议在 IDE 里直接编辑并保存） |
| .env 误提交 | 已加 .gitignore，若 `git add -f .env` 提交过，立即从仓库移除并**更换密钥** |
| 模型下载慢 | 检查 `HF_ENDPOINT` 是否为 `https://hf-mirror.com`，改后重启 |
| 接口文档不同步 | 后端改了接口记得同步更新 `docs/api.md`，见团队硬性约定 |
