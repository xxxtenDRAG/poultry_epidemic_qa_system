# 开发环境搭建指南

> 适用：Windows（PowerShell）· 项目根目录 `d:\code\poultry_epidemic_qa_system`
> 对应《详细实施方案》2.2「环境与工具统一」与阶段 0 检查点。

---

## 1. 环境要求

| 组件 | 要求 | 检查命令 |
|------|------|----------|
| Python | **推荐 3.11**（本机是 3.14 也可先用，出兼容问题再换） | `python --version` 或 `py -0p` |
| Node.js | 18+ | `node -v` |
| npm | 随 Node 自带 | `npm -v` |
| Docker Desktop | 可选（用于起 MySQL） | `docker --version` |
| Git | 可选（版本管理） | `git --version` |

---

## 2. 后端依赖安装（Python venv）

### 2.1 创建虚拟环境

```powershell
cd backend

# 推荐用 py 启动器指定 3.11；若只有默认版本可省略 -3.11
py -3.11 -m venv venv

# 激活虚拟环境（提示符前出现 (venv) 即成功）
.\venv\Scripts\Activate.ps1
```

> 若提示"禁止运行脚本"：
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> ```

### 2.2 安装依赖

```powershell
python -m pip install --upgrade pip

# 先装 CPU 版 torch（约 200MB；默认版会带 CUDA，需 2GB+，练手用不上 GPU）
pip install torch --index-url https://download.pytorch.org/whl/cpu

# 再装其余全部依赖（requirements.txt 会自动跳过已装好的 torch）
pip install -r requirements.txt
```

> 如果嫌 torch 分开装麻烦，也可以一条命令全部装：
> ```powershell
> pip install -r requirements.txt
> ```
> 完整安装包含 llama-index / langgraph / chromadb / sentence-transformers 等，
> 耗时可长达 10 分钟，属正常现象，请耐心等待。

### 2.3 退出虚拟环境

```powershell
deactivate
```

---

## 3. 前端依赖安装

```powershell
cd frontend
npm install
```

> 国内网络较慢可先设置镜像源再安装：
> ```powershell
> npm config set registry https://registry.npmmirror.com
> ```

---

## 4. MySQL（可选）

方案中 MySQL 用于存会话与文档元数据（阶段 1 起用）。两种方式任选：

- **方式一（推荐，Docker）**：
  ```powershell
  docker compose -f docker/docker-compose.yml up -d mysql
  ```
- **方式二（本机安装）**：下载 MySQL 8.x 安装包，库名 `goose_qa`，账号密码与 `.env` 中 `MYSQL_*` 保持一致。

---

## 5. 环境变量配置

复制模板并填入真实密钥（**严禁提交 Git**）：

```powershell
Copy-Item .env.example .env
```

在 `.env` 中只需填 `DEEPSEEK_API_KEY`；向量化/精排走本地 bge 模型，无需 API Key。

**bge 模型首次使用会从 HuggingFace 下载**（约 100MB），国内可走镜像加速：

```powershell
$env:HF_ENDPOINT = 'https://hf-mirror.com'
```

> 注意：此设置只在当前终端生效，重启终端需重新执行。

---

## 6. 验证方法

### 6.1 后端验证

终端 1（先激活 venv）：

```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

验证项：

| 验证 | 操作 | 期望结果 |
|------|------|----------|
| 服务启动 | 观察启动日志 | 无报错，显示 `Uvicorn running on http://127.0.0.1:8000` |
| Swagger 文档 | 浏览器打开 `http://localhost:8000/docs` | 显示 4 个接口（chat/documents/graph/health） |
| 健康检查 | 浏览器打开 `http://localhost:8000/api/health` | 返回 `{"status":"ok",...}` |
| 单元测试 | 另开终端执行 `cd backend; .\venv\Scripts\Activate.ps1; python -m pytest` | 显示 `1 passed` |

### 6.2 前端验证

终端 2：

```powershell
cd frontend
npm run dev
```

验证项：浏览器打开 `http://localhost:5173`，左侧菜单可切换对话/文档管理/知识图谱/会话历史 4 个页面。

---

## 7. 常见问题

| 问题 | 解决方案 |
|------|----------|
| `Form data requires "python-multipart"` | `pip install python-multipart`（已加入 requirements.txt，重装依赖即可） |
| venv 激活被禁止 | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| 模型下载慢/失败 | 安装前执行 `$env:HF_ENDPOINT = 'https://hf-mirror.com'` |
| Python 3.14 下某包安装失败 | 建议改用 3.11：`py -3.11 -m venv venv` 重建环境 |
| 端口被占用 | 换端口：`uvicorn main:app --reload --port 8001`（前端代理需同步改 vite.config.js） |

---

## 8. 一键安装速查

```powershell
# 后端
cd backend
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# 前端
cd ..\frontend
npm install

# 启动验证（两个终端）
# 终端1: cd backend; .\venv\Scripts\Activate.ps1; uvicorn main:app --reload --port 8000
# 终端2: cd frontend; npm run dev
```
