# 四层架构与项目文件图

## 状态与边界

本项目采用方案一：目录显式对应四层架构。前后端分离开发、单体后端、本机单用户；演示时由 FastAPI 提供静态前端和 API。四层是职责边界，不是四个进程或微服务。

**本次仅重排目录、导入和文档，没有实现业务功能。** 当前可用：页面布局、健康检查、静态资源托管、固定本地身份和 SQLAlchemy 连接工厂。未实现：数据库实体/建表、专题、上传、任务、RAG、引用、笔记、外部模型调用。

## 四层与目录一一对应

| 层 | 位置 | 负责 | 不负责 |
|---|---|---|---|
| ① 界面层 | `frontend/src/` | 页面、交互、请求与响应展示 | 数据库直连、密钥管理、最终授权 |
| ② 应用层 | `backend/app/application/` | 产品用例、资源范围校验、生命周期和持久化编排 | HTTP 格式细节、供应商协议 |
| 应用层的 HTTP 入口 | `backend/app/api/` | 请求/响应类型、路由、协议适配 | 自己实现检索和文件存储 |
| ③ AI 处理层 | `backend/app/intelligence/` | 文本处理、检索融合、上下文/提示词、生成与引用策略 | 用户授权、产品任务状态、数据库事务 |
| ④ 数据与外部服务层 | `backend/app/infrastructure/` | SQLite、文件、向量库、模型客户端、任务执行机制 | 决定产品流程或检索策略 |

`main.py` 是组装入口，`config.py` 是公共配置，不是第五个业务层。后台任务执行器也不是额外业务层：执行机制在第四层，导入任务的规则和生命周期在第二层。

```text
界面层 frontend
       │ HTTP / 未来流式响应
       ▼
应用入口 api → application
                    ├─────────────→ infrastructure
                    ▼                    ▲
               intelligence ────────────┘
```

### 依赖规则

- API 通过 application 执行业务；当前健康检查是无业务的独立入口。
- application 可以调用 intelligence 和 infrastructure，不能导入 api 或 main。
- intelligence 可以使用第四层适配器，不能导入 application、api 或 main。
- infrastructure 不导入上层，不决定资料是否有权被用户访问；仍须验证文件路径、必要查询范围等技术约束。
- `main.py` 可组装所有层；各层可读无副作用的 `config.py`。
- 当前不用抽象工厂/接口基类包裹每个占位模块。实际调用关系形成后，再按测试替身和供应商替换需求增加必要接口。
- `tests/test_architecture.py` 检查后三层的 Python 静态向上导入；这是结构约束，不是安全隔离证明，也不覆盖动态导入。

## 当前文件图

以下均为实际存在的源码或文档；标记“待实现”的模块只有职责说明，并没有伪造业务接口。

```text
knowledge_base_agent/
├── README.md                         # 唯一上手入口、四层导航
├── .gitignore
├── frontend/                         # ① 界面层
│   ├── package.json / package-lock.json
│   ├── index.html / tsconfig.json / vite.config.ts
│   └── src/
│       ├── main.tsx / App.tsx
│       ├── types.ts / styles.css
│       ├── api/index.ts              # 请求封装与健康检查
│       ├── hooks/useBackendHealth.ts
│       ├── pages/
│       │   ├── NotebooksPage.tsx      # 专题首页骨架
│       │   └── WorkbenchPage.tsx      # 三栏工作台骨架
│       └── components/
│           ├── sources/SourcesPanel.tsx
│           ├── chat/ChatPanel.tsx
│           ├── citations/CitationPanel.tsx
│           ├── notes/NotesPanel.tsx
│           └── common/EmptyState.tsx
├── backend/
│   ├── pyproject.toml / uv.lock / .python-version
│   ├── .env.example                  # 模型配置模板，当前未加载
│   ├── app/
│   │   ├── main.py                   # 组装与启动、静态前端托管
│   │   ├── config.py                 # 公共配置与项目相对路径
│   │   ├── api/                      # 应用层 HTTP 入口
│   │   │   ├── router.py
│   │   │   ├── schemas.py            # 已有健康响应；业务 DTO 待实现
│   │   │   ├── health.py             # 已实现 GET /api/health
│   │   │   ├── notebooks.py          # 待实现接口
│   │   │   ├── sources.py            # 待实现接口
│   │   │   ├── chat.py               # 待实现接口
│   │   │   └── notes.py              # 待实现接口
│   │   ├── application/              # ② 应用层
│   │   │   ├── identity.py           # 已有固定本地身份，不是真实认证
│   │   │   ├── notebooks.py          # 待实现专题用例
│   │   │   ├── sources.py            # 待实现资料用例与资源范围检查
│   │   │   ├── ingestion.py          # 待实现导入编排与状态生命周期
│   │   │   ├── chat.py               # 待实现会话用例、RAG 编排与保存
│   │   │   └── notes.py              # 待实现笔记保存、编辑、导出
│   │   ├── intelligence/             # ③ AI 处理层
│   │   │   ├── parsing.py            # 待实现 PDF/MD/TXT 文本解析
│   │   │   ├── chunking.py           # 待实现切片、稳定 ID 与位置
│   │   │   ├── retrieval.py          # 待实现 BM25/向量融合与精排策略
│   │   │   ├── generation.py         # 待实现上下文、提示词、生成流程
│   │   │   └── citations.py          # 待实现引用编号、映射、快照构造
│   │   └── infrastructure/           # ④ 数据与外部服务层
│   │       ├── database/
│   │       │   ├── connection.py     # 已有 SQLAlchemy 连接工厂
│   │       │   └── models.py         # 八类实体定义待实现，未建表
│   │       ├── storage/local_files.py# 原文件存取适配，待实现
│   │       ├── vector/chroma.py      # 向量写入/查询/删除适配，待实现
│   │       ├── models/
│   │       │   ├── llm.py            # 模型 API 客户端，待实现
│   │       │   ├── embedding.py      # Embedding API 客户端，待实现
│   │       │   └── reranker.py       # 精排 API 客户端，待实现
│   │       └── tasks/local_runner.py # 进程内任务执行机制，待实现
│   └── tests/
│       ├── test_scaffold.py          # 原骨架行为回归测试
│       └── test_architecture.py      # 层依赖、模块加载、连接迁移检查
├── data/                             # 运行数据，不是代码层
│   ├── README.md / .gitignore
│   ├── uploads/.gitkeep
│   └── chroma/.gitkeep
├── docs/
│   ├── architecture.md              # 本文
│   └── demo-checklist.md
├── samples/README.md
└── scripts/run_local.sh
```

包标记 `__init__.py`、缓存和依赖目录省略展示。`data/app.sqlite3` 未创建。方案草图中的 `prompts.py`、`database/repositories.py` 暂不建空文件：提示词实际出现时再从 generation 拆出；真实 SQL 读写实现时再建立 repositories。数据库实体 `database/models.py` 与模型客户端 `infrastructure/models/` 含义不同，按父目录区分。

## 按功能快速定位

| 问题 | 首先看哪里 |
|---|---|
| 上传按钮或来源列表 | `frontend/src/components/sources/` |
| 上传接口参数 | `backend/app/api/sources.py`、`api/schemas.py` |
| 文件能否上传、属于哪个专题 | `backend/app/application/sources.py` |
| 导入何时 ready、失败后怎样重试 | `backend/app/application/ingestion.py` |
| 原始文件实际如何保存 | `backend/app/infrastructure/storage/local_files.py` |
| 文本解析/切片 | `backend/app/intelligence/parsing.py`、`chunking.py` |
| 查询向量库的 SDK 调用 | `backend/app/infrastructure/vector/chroma.py` |
| BM25 与向量怎样融合 | `backend/app/intelligence/retrieval.py` |
| 提示词、证据如何组成回答 | `backend/app/intelligence/generation.py` |
| LLM 地址、请求、超时和传输异常 | `backend/app/infrastructure/models/llm.py` |
| 引用编号怎样对应片段 | `backend/app/intelligence/citations.py` |
| 会话与回答怎样保存 | `backend/app/application/chat.py` |
| 数据库连接、数据表 | `backend/app/infrastructure/database/` |

## 本次路径迁移

| 原路径（相对 backend/app） | 新路径 | 说明 |
|---|---|---|
| `services/` | `application/` | 应用用例层 |
| `database.py` | `infrastructure/database/connection.py` | 原连接函数不变 |
| `models.py` | `infrastructure/database/models.py` | 保持实体占位，不建表 |
| `schemas.py` | `api/schemas.py` | DTO 属于传输协议 |
| `api/routes/*.py` | `api/*.py` | 移除多余嵌套，路由不变 |
| `rag/parsers.py` | `intelligence/parsing.py` | 解析策略 |
| `rag/chunking.py` | `intelligence/chunking.py` | 切片策略 |
| `rag/retrieval.py` | `intelligence/retrieval.py` | 检索策略；存储接口归基础设施 |
| `rag/citations.py` | `intelligence/citations.py` | 引用策略 |
| `rag/pipeline.py` | `intelligence/generation.py` | 生成流程，会话持久化由应用层负责 |
| `rag/indexing.py` | `application/ingestion.py` | 跨 SQL/向量库的导入编排 |
| `rag/providers.py` | `infrastructure/models/` | 拆分原有 LLM/Embedding/Reranker 职责占位 |
| `services/sources.py` 内文件/任务职责 | `infrastructure/storage/`、`infrastructure/tasks/` | 拆分原有职责说明，无新业务实现 |

前端 `src/api.ts` 移到 `src/api/index.ts`，对调用方的 `../api` 导入方式和 HTTP 行为不变。公共 config 和启动脚本路径不变；无新增运行依赖，也不改模型配置。

## 后续实现时的约束

- SQLite 保存 notebooks、sources、chunks、conversations、messages、citations、notes、jobs；Chroma 仅为可重建索引。
- 导入成功后才标记 ready；重试幂等，中间失败的索引不得用于问答。
- BM25 与向量检索共同受已验证且 ready 的来源范围约束。
- 生成与引用展示共用同一次检索结果；编号有效不代表语义有依据。
- 仅固定本地身份，不接受客户端 owner，不宣称已实现多租户隔离。
- 模型失败明确报错，不降级成无资料依据的普通回答。
- 原文、用户笔记和 AI 产物区分保存，不自动将笔记重新入库。

## 验证与恢复

运行 README 中的后端测试、前端构建和脚本语法检查。健康响应仍为 `business_ready: false`；业务路由仍未实现。结构测试不替代未来业务验收。

本次调整前的源码归档、SHA256、接口快照、差异和命令日志保存在本地被忽略的 `reports/four-layer/`，不提交凭据或运行数据。调整前 Git 提交为 `2568404`。如需在已推送分支撤回目录调整，先保存后续工作，再对本次重构提交执行 `git revert`，而非强推覆盖历史。

旧版与学习笔记仍在仓库外；本次不触碰 `knowledge_base_agent_legacy`、`learning-notes` 或原始资料。旧版整理备份见旧归档的 `.migration-backup`；不要用旧重建脚本清理新版。
