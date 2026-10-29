# 知识研究工作台

面向个人学习与研究的来源驱动 AI 工作台：专题组织资料，对话帮助理解，引用支持核验，笔记沉淀成果。

> **当前阶段：工程骨架。** 已有页面布局、健康检查、静态前端托管和基础测试。专题、上传、RAG、引用与笔记业务尚未实现；界面中的待实现功能不会返回假成功。

## 技术与目录

- 前端：React、TypeScript、Vite、Tailwind CSS。
- 后端：FastAPI、SQLAlchemy；SQLite 连接工厂已准备，尚未建表。
- 计划接入：Chroma、Embedding、LLM、可选 Reranker，当前没有模型调用。
- 运行范围：**仅本机单用户**，不具备真实登录、多租户隔离或公网部署条件。

```text
frontend/   前端页面、组件、请求封装
backend/    HTTP 接口、业务服务、RAG、测试
data/       新版运行数据（不提交用户文件或数据库）
docs/       工程架构与演示验收说明
samples/    公开演示资料（目前只有说明）
scripts/    统一启动入口
```

详细结构见 [架构与文件图](docs/architecture.md)，功能边界见 [演示验收清单](docs/demo-checklist.md)。

旧版已独立归档到同级 `knowledge_base_agent_legacy`，学习笔记保留在同级 `learning-notes`；它们均不属于本 Git 仓库，新版不依赖它们启动。

## 安装

前置条件：uv、Python 3.12、Node.js（`^20.19.0 || >=22.12.0`）、npm。以下命令在本仓库根目录执行。

```bash
(cd backend && uv sync --frozen)
(cd frontend && npm ci && npm run build)
bash scripts/run_local.sh
```

浏览器打开 <http://127.0.0.1:8765>。Ctrl+C 停止服务。当前无需 API Key；`backend/.env.example` 只是未来配置模板，尚未加载。

开发时，在后端运行的基础上另开终端：

```bash
cd frontend
npm run dev
```

访问 <http://127.0.0.1:5173>，Vite 将 `/api` 请求代理至本地后端。

## 验证

```bash
(cd backend && .venv/bin/python -m pytest -q)
(cd frontend && npm run build)
bash -n scripts/run_local.sh
```

`GET /api/health` 返回 `stage: scaffold` 和 `business_ready: false`，仅代表进程存活，不代表问答功能可用。

## 数据与安全边界

- 本地固定身份不是用户认证，不要将服务暴露至公网。
- 密钥、上传资料、SQLite 数据库、向量库、依赖目录和日志不得提交。
- 原始文件将放在 `data/uploads`，向量索引放在 `data/chroma`；业务库计划为 `data/app.sqlite3`。
- `docs` 是工程文档，不自动作为知识库资料。学习笔记需要用户主动上传。
- 不复制旧版 `.env`、数据库或历史问答到本仓库。

## 下一步

按“专题创建 → 上传解析 → 真实问答与引用 → 笔记与导出”的顺序实现。优先跑通一条真实链路，不引入注册、协同、微服务或复杂 Agent 编排。
