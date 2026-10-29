# 知识研究工作台

面向个人学习与研究的来源驱动 AI 工作台。当前已完成：**专题 → 上传解析 → 手动索引 → 勾选来源 → 流式问答 → 点击引用 → 保存笔记 → 编辑 → 导出 Markdown**。

## 当前能力

- 本地 SQLite 保存专题、资料、片段、任务、会话、消息、引用和笔记，共八张业务表。
- PDF / Markdown / TXT 上传、后台解析、去重、失败重试与中断恢复。
- 手动向量索引：独立索引状态、模型配置标识、维度校验、版本切换和重试幂等。
- Chroma 向量 + 中文分词 BM25 + RRF，可选 Reranker；两路检索共同受已选来源约束。
- 多轮对话、流式回答、停止生成、有限历史、请求幂等、引用快照。
- 独立笔记、Markdown 编辑/预览、自动/手动保存、版本冲突保护和导出。
- 资料不足时要求模型明确说明；不把“有引用”等同于答案正确。

**未实现**：联网搜索、注册登录、多用户隔离、协作、OCR、通用自主 Agent。仅本机单用户，不要部署公网。

## 四层导航

| 层 | 代码位置 | 职责 |
|---|---|---|
| ① 界面 | `frontend/src/` | 专题、资料、索引操作、对话、引用面板 |
| ② 应用 | `backend/app/application/`；入口 `backend/app/api/` | 资源范围、任务、索引编排、消息保存 |
| ③ AI 处理 | `backend/app/intelligence/` | 解析切片、混合检索、提示词、生成和引用规则 |
| ④ 基础设施 | `backend/app/infrastructure/` | SQLite、原文件、Chroma、后台执行、模型 HTTP 客户端 |

[完整架构](docs/architecture.md) · [资料入库接口](docs/ingestion.md) · [索引、问答与模型配置](docs/research.md) · [笔记使用说明](docs/notes.md) · [验收记录](docs/testing.md)

## 安装与启动

支持 macOS / Linux，Python 3.12、uv、Node.js（`^20.19.0 || >=22.12.0`）、npm。命令在仓库根目录执行：

```bash
(cd backend && uv sync --frozen)
(cd frontend && npm ci && npm run build)
bash scripts/run_local.sh
```

打开 <http://127.0.0.1:8765>。开发前端另开终端运行 `(cd frontend && npm run dev)`，访问 <http://127.0.0.1:5173>。

首次启动建立 schema v3；旧 v1/v2 数据库升级前会自动保存本地备份，然后事务化迁移。仅允许单个后端进程使用同一数据目录。不要添加 `--workers`。

## 模型配置

本机 `backend/.env`（已被 Git 忽略）可独立设置三个服务：

| 用途 | 服务 | 本轮验证配置 |
|---|---|---|
| LLM | DeepSeek 官方 | `deepseek-flash`，`https://api.deepseek.com` |
| Embedding | SiliconFlow | `Qwen/Qwen3-Embedding-8B`，4096 维 |
| Reranker | SiliconFlow | `Qwen/Qwen3-Reranker-8B` |

参考 `backend/.env.example`。也可用 `WORKBENCH_MODEL_ENV` 指向已有本地配置，仅导入配置值，不复制密钥到源码。环境变量 > 新版 `.env` > 被引用配置。改完配置后重启应用。

**不同服务的 Key 不能混用。** 指向不同地址但没有显式设置对应 Key 时，不把原供应商 Key 转发过去。当前本机已配置的实际 Key 不在 Git 中；克隆仓库后需自行配置。

显式验证服务（会发送少量合成文本并产生 API 消费）：

```bash
backend/.venv/bin/python scripts/verify_models.py
```

默认输出脱敏结果到被忽略的 `reports/rag/latest-model-check.json`；只输出主机、模型名、维度和测试结果，不输出密钥。解析文件不调用模型；点击建立索引或发送问题才调用服务。

## 演示步骤

1. 创建专题，上传 `samples/budget-a.md`、`samples/budget-b.md`。
2. 等待解析完成，分别点击“建立索引”，等待“可检索”。
3. 只勾选 A，提问预算；只勾选 B，再提问；同时选择两份比较冲突。
4. 点击回答的 `[S1]` 等按钮，核对原文、页码或文本位置。
5. 点击完整回答下的“保存为笔记”，修改标题/正文，预览并导出 Markdown。
6. 刷新或重启，确认会话、引用和笔记仍在。笔记功能不增加模型调用。

模型输出会变化，样例通过不等于通用准确率。切换 Embedding 模型/维度后旧索引不兼容，必须重新索引；应用不会混用旧向量。

## 验证与数据

```bash
(cd backend && .venv/bin/python -m pytest -q)
(cd frontend && npm test && npm run build)
bash -n scripts/run_local.sh
```

自动化测试使用临时目录、可控模型替身，并包含真实本地 Chroma 操作；不会调用付费服务。真实模型检查需显式运行上述脚本。

- 业务库：`data/app.sqlite3`；原文件：`data/uploads`；向量：`data/chroma`。
- `WORKBENCH_DATA_DIR` 可指定独立绝对路径用于演示或测试。
- 停止服务后备份整个数据目录；不要只复制向量库或使用旧版重建脚本。
- 健康接口的 `qa_ready` 仅表示必要模型配置存在，不保证实时网络、额度或服务健康；`business_ready=false` 是保留的发布就绪标志，不将本机 MVP 视为已通过生产部署验收。
- 密钥、原文件、数据库、日志、截图、依赖和构建产物均不提交 Git。
