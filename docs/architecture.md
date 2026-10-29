# 四层架构与文件图

## 当前状态

本机单用户、单体 Python 后端。前端和后端分离开发；演示时 FastAPI 同时提供前端静态资源和 API。

已完成专题、上传、解析切片、持久化和任务恢复。未接入模型、向量索引、问答、引用生成或笔记。

## 层与依赖

| 层 | 位置 | 责任 |
|---|---|---|
| ① 界面 | `frontend/src` | 页面、表单、状态轮询、片段展示 |
| ② 应用 | `backend/app/application`；入口 `backend/app/api` | 产品用例、资源范围、去重与重试规则、导入生命周期 |
| ③ AI 处理 | `backend/app/intelligence` | 当前为确定性的解析、切片；未来为检索与生成策略 |
| ④ 基础设施 | `backend/app/infrastructure` | 数据库、文件 IO、后台执行、未来外部服务适配 |

```text
frontend → HTTP api → application
                           ├→ intelligence（字节/文本 → 解析和切片结果）
                           └→ infrastructure（持久化/任务执行）
```

- API 不执行 SQL、不直接保存文件，调用应用用例并过滤响应字段。
- application 不导入 FastAPI，持久化通过 Repository、文件通过 LocalFiles；不直接读写磁盘。
- intelligence 不知道用户、数据库或任务状态；解析函数接收字节，返回带位置的文本。
- infrastructure 不导入上层。LocalRunner 接收回调，实际回调在 main 中注入；任务规则仍由 application 决定。
- main 是组装入口，config 是公共配置；不是额外业务层。
- 导入 Python 模块无建表、启动线程、模型或文件写入副作用；运行时初始化只在 lifespan 内完成。
- 静态架构测试检查后三层禁止向上导入；不将此当作安全审计或动态导入验证。

## 文件图

```text
knowledge_base_agent/
├── frontend/
│   └── src/
│       ├── App.tsx                       # hash 路由，刷新保留所选专题
│       ├── api/index.ts                  # HTTP 客户端与错误解析
│       ├── types.ts / styles.css
│       ├── hooks/useBackendHealth.ts
│       ├── pages/
│       │   ├── NotebooksPage.tsx         # 创建与列出专题
│       │   └── WorkbenchPage.tsx         # 上传、轮询、详情、重试、片段分页
│       └── components/
│           ├── sources/SourcesPanel.tsx # 资料选择与状态
│           └── ...                      # 问答/笔记/引用组件仍为未接入占位
├── backend/
│   ├── pyproject.toml / uv.lock          # 新增 pypdf，无模型依赖
│   ├── app/
│   │   ├── main.py                      # 生命周期、组装、异常响应、静态前端
│   │   ├── config.py                    # 路径、大小/页数/文本/切片限制
│   │   ├── api/
│   │   │   ├── router.py / schemas.py
│   │   │   ├── health.py
│   │   │   ├── notebooks.py             # 专题创建、列表、详情
│   │   │   ├── sources.py               # 上传、列表、详情/任务、片段、重试
│   │   │   └── chat.py / notes.py       # 未实现业务路由
│   │   ├── application/
│   │   │   ├── identity.py              # 固定本地身份
│   │   │   ├── errors.py                # 不依赖 HTTP 框架的应用错误
│   │   │   ├── notebooks.py             # 专题用例
│   │   │   ├── sources.py               # 上传校验、去重、文件补偿、查询和重试
│   │   │   ├── ingestion.py             # 恢复、领取、解析、切片、完成/失败
│   │   │   └── chat.py / notes.py       # 未实现
│   │   ├── intelligence/
│   │   │   ├── parsing.py               # UTF-8 文本、文本型 PDF、页码
│   │   │   ├── chunking.py              # 稳定 ID、页内字符位置、重叠切片
│   │   │   └── retrieval.py / generation.py / citations.py # 未实现
│   │   └── infrastructure/
│   │       ├── database/
│   │       │   ├── connection.py        # SQLite 外键、忙等待、连接工厂
│   │       │   ├── models.py            # 四张业务表的 SQLAlchemy 映射
│   │       │   ├── repositories.py      # 短事务、会话、约束、领取/保存
│   │       │   ├── migrate.py           # 一次性版本化启动迁移
│   │       │   └── migrations/001_initial.sql
│   │       ├── storage/local_files.py   # 临时文件、原文件、校验、启动清理
│   │       ├── tasks/local_runner.py    # 单工作线程、进程锁、优雅停止
│   │       ├── vector/chroma.py         # 未实现、不连接
│   │       └── models/                  # LLM/Embedding/Reranker 未实现、不调用
│   └── tests/
│       ├── conftest.py                  # 临时目录 fixture
│       ├── test_scaffold.py             # 健康、静态资源、身份等回归测试
│       ├── test_architecture.py         # 依赖方向、模块加载、连接检查
│       └── test_ingestion.py            # 实际资料链路与故障注入
├── data/                               # 被忽略的 SQLite、原文件等
├── docs/                               # 工程文档，不参与检索
├── samples/                            # 原创、可公开演示文本
└── scripts/run_local.sh
```

## 数据模型

| 表 | 核心字段/约束 |
|---|---|
| notebooks | id、owner_id、name、时间；名称 1～100 字符，可同名 |
| sources | notebook_id、filename、kind、size_bytes、sha256、storage_key、状态、页/片段数、错误；专题+哈希唯一 |
| chunks | source_id、ordinal、text、page_start/end、char_start/end；来源+序号唯一 |
| jobs | source_id、notebook_id、owner_id、状态/阶段/错误、时间；同来源至多一个 queued/running 任务 |

schema 版本保存在 SQLite `user_version=1`，不是第五张业务表。首次迁移显式事务化执行 SQL；未知版本或未带版本的非空库拒绝覆盖。后续 schema 变化必须添加新迁移，不能只改 models 或修改已应用的 001。

## 状态与数据流

```text
上传：专题校验 → 类型/大小 → 临时文件与 SHA256 → 去重
     → 原文件落盘 → 同一事务登记 source + job → 返回 202

后台：数据库领取 queued → parsing → 解析 → chunking
     → 同一事务替换片段、标记 source=parsed / job=succeeded

异常：source=failed / job=failed → 用户重试 → 新 job（保留失败历史）
```

资料成功仅代表 parsed；接口显示 `index_status=not_indexed`。PDF 切片不跨页，字符位置是提取后页内文本的 Unicode 字符偏移（左闭右开），不是 PDF 像素坐标；TXT/MD 是去除可选 UTF-8 BOM 后的全文字符位置，无伪造页码。

## 一致性与恢复

- 单进程文件锁在迁移、恢复、接收请求前获取，避免两个执行器同时修改同一库。文件锁适用于 macOS/Linux，非分布式锁。
- 原文件落盘失败不登记任务；数据库登记失败清理本次文件；并发重复登记由数据库唯一约束兜底，清理多余副本。
- 崩溃遗留的 `.pending/*.part` 与没有数据库来源记录的 32 位 ID 文件，只在下次启动、加锁后清理；不扫描或删除其他目录。
- queued 任务持久化，重启继续领取；running/parsing 标记中断，等待显式重试。
- 缺失原文件标记失败；重试前检查存在，执行前检查大小/哈希；变更原文件不会静默产生新片段。
- 切片保存失败整体回滚，不留半套 parsed 数据；失败记录保留。
- 所有 API 来源访问先检查专题和固定本地 owner；前端不能指定 owner。此设计不等于真实认证或多用户安全。

## 扩展边界

后续接入向量化时增加独立索引状态，不能把 parsed 当 ready。模型/检索模块仍保留在相应层。本轮不创建消息、会话、引用或笔记表，不自动导入旧版文件与密钥。
