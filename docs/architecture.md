# 架构与项目文件图

## 决策

前后端分离开发，单体后端，本机单用户。演示时 FastAPI 提供前端构建产物和 API，只需一个服务进程。新版不运行旧版 Streamlit，不读取旧库；旧项目留在仓库外归档。

只保留必要的层次：

```text
React 页面 → HTTP API → services → SQLite / 原文件 / rag
                                                    ↓
                                           Chroma / 模型 API
```

这是目标调用关系，目前只有页面骨架、API 健康检查和数据库连接工厂可用；以下业务模块均为职责占位，尚未完成业务实现。

## 文件图

```text
knowledge_base_agent/
├── README.md                         # 唯一上手入口
├── .gitignore                        # 密钥、数据、缓存、构建产物排除规则
├── frontend/
│   ├── package.json / package-lock.json
│   ├── index.html
│   ├── tsconfig.json
│   ├── vite.config.ts                # React/Tailwind、开发 API 代理
│   └── src/
│       ├── main.tsx                  # 挂载入口
│       ├── App.tsx                   # 页面切换与连接状态
│       ├── api.ts                    # 统一 HTTP 请求与健康检查
│       ├── types.ts                  # 共享类型
│       ├── styles.css
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
│   ├── pyproject.toml / uv.lock
│   ├── .python-version
│   ├── .env.example                  # 模板占位，尚未接入配置读取
│   ├── app/
│   │   ├── main.py                   # FastAPI、静态前端托管
│   │   ├── config.py                 # 项目相对路径，不依赖 shell cwd
│   │   ├── database.py               # SQLAlchemy 连接工厂
│   │   ├── models.py                 # 待实现八类业务实体
│   │   ├── schemas.py                # 健康响应；业务 DTO 待实现
│   │   ├── api/
│   │   │   ├── router.py
│   │   │   └── routes/
│   │   │       ├── health.py         # 已实现
│   │   │       ├── notebooks.py      # 待实现专题接口
│   │   │       ├── sources.py        # 待实现资料接口
│   │   │       ├── chat.py           # 待实现问答/引用接口
│   │   │       └── notes.py          # 待实现笔记/导出接口
│   │   ├── services/
│   │   │   ├── identity.py           # 固定本地身份，不是真实认证
│   │   │   ├── notebooks.py          # 待实现专题管理
│   │   │   ├── sources.py            # 待实现上传、文件、导入任务、状态
│   │   │   ├── chat.py               # 待实现范围校验、会话、RAG 编排
│   │   │   └── notes.py              # 待实现笔记、引用快照、导出
│   │   └── rag/
│   │       ├── parsers.py            # 待实现 PDF/MD/TXT 解析
│   │       ├── chunking.py           # 待实现稳定片段 ID 与位置
│   │       ├── indexing.py           # 待实现幂等索引写入
│   │       ├── providers.py          # 待实现模型适配
│   │       ├── retrieval.py          # 待实现过滤、混合检索、精排
│   │       ├── citations.py          # 待实现编号、片段映射与快照
│   │       └── pipeline.py           # 待实现固定 RAG 流程与流式生成
│   └── tests/test_scaffold.py
├── data/
│   ├── README.md / .gitignore
│   ├── uploads/.gitkeep
│   └── chroma/.gitkeep
├── docs/
│   ├── architecture.md               # 本文
│   └── demo-checklist.md             # 验收与演示边界
├── samples/README.md                 # 仅存公开可发布的测试资料
└── scripts/run_local.sh              # 仅监听 127.0.0.1
```

省略包标记 `__init__.py`；未列出本地依赖、缓存与构建产物。`data/app.sqlite3` 尚未创建。当前不需要独立 repositories、storage、tasks、core 目录；复杂度实际增长后再拆。

## 数据与流程约束（待业务实现时逐项验证）

SQLite 保存 notebooks、sources、chunks、conversations、messages、citations、notes、jobs。Chroma 仅为可重建检索索引。

- 导入：校验 → 存文件/任务 → 解析切片 → 写索引 → 全部成功才标记 ready。中断可重试，不能重复入库。
- 问答：校验专题与所选来源 → 有限历史改写 → 同范围 BM25/向量 → RRF/可选精排 → 编号引用 → 流式回答 → 持久化。
- 引用：生成和展示使用同一次检索结果；无效编号不渲染成有效证据。编号正确不代表语义必然正确。
- 身份：服务端提供本地 owner，不接受客户端任意 owner；这不是经过验证的多租户隔离。
- 文件：按服务端 ID 保存，不接受任意文件系统路径；API Key 不进入前端。
- 故障：模型失败明确报错，不降级成无资料依据的回答。
- 笔记：区分原文、用户笔记与 AI 产物，不自动重新入库。

## 归档与恢复

旧源码、旧资料、旧数据库和旧配置留在同级 `knowledge_base_agent_legacy`。整理前的新骨架副本保存在该归档下的 `.migration-backup`，本地迁移日志和哈希清单位于归档的 `reports/reorganization`；它们不上传新版 Git 仓库。

恢复旧版运行方式：停止新版服务，进入旧版归档，用原 Python 环境运行其 `app.py`。不要用旧版 `rebuild_db.py` 清理新版数据。

如果需要撤回本次目录分离，先备份当前新版；在额外目录复制旧版归档，再合入 `.migration-backup` 的前后端、数据目录、脚本与原文件图。不要直接覆盖正在开发的新版。旧版密钥原位保留，恢复时不得公开或提交。
