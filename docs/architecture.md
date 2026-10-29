# 四层架构与研究链路

## 状态

已实现本机单用户资料入库、手动向量索引、限定来源问答、引用和会话持久化。没有联网搜索、笔记编辑、多用户认证或独立微服务。

## 层级与依赖

```text
① frontend → HTTP API（② 的协议入口）→ ② application
                                         ├→ ③ intelligence
                                         └→ ④ infrastructure
③ intelligence → 按注入的客户端使用④，不能反向依赖②或 API
④ infrastructure → 不导入上层
```

- API：DTO、路径、错误响应、SSE 转发。不能自行决定检索范围或执行 SQL。
- application：用户/专题范围、导入/索引状态、会话与消息生命周期、故障恢复。
- intelligence：文本解析、切片、中文分词、检索融合、上下文、提示词、引用标记处理。
- infrastructure：数据库与短事务、文件 IO、Chroma、模型协议、进程内任务执行机制。
- `main.py` 是组装和生命周期入口，`config.py` 是公共配置，不是额外业务层。
- Python 静态架构测试阻止后三层向上导入；测试不覆盖动态导入，也不是安全隔离证明。

## 文件导航

```text
frontend/src/
├── App.tsx                         # 专题 hash 路由与应用导航
├── api/index.ts                    # HTTP、POST SSE 解码与错误处理
├── pages/NotebooksPage.tsx          # 专题创建、列表
├── pages/WorkbenchPage.tsx         # 上传、解析/索引状态、来源勾选
└── components/
    ├── sources/SourcesPanel.tsx    # 原文查看、建立/重建索引、问答范围
    ├── chat/ChatPanel.tsx          # 会话、流式输出、停止、历史
    └── citations/CitationPanel.tsx# 保存的引用快照与位置

backend/app/
├── main.py                         # 生命周期、依赖组装、错误响应
├── config.py                       # 本地路径及文件处理限制
├── api/
│   ├── router.py / schemas.py
│   ├── health.py                   # 配置/能力标识，不探测余额
│   ├── notebooks.py / sources.py  # 资料和索引接口
│   ├── chat.py                     # 会话/消息 API、SSE、断开清理
│   └── notes.py                    # 未实现
├── application/
│   ├── identity.py / errors.py
│   ├── notebooks.py / sources.py  # 专题、资料和归属校验
│   ├── ingestion.py                # 原文件 → 解析 → 片段保存
│   ├── indexing.py                 # 片段 → Embedding → 向量校验 → ready
│   ├── chat.py                     # 范围、幂等、历史、RAG、持久化
│   └── notes.py                    # 未实现
├── intelligence/
│   ├── parsing.py / chunking.py
│   ├── retrieval.py                # jieba/BM25 + 向量 → RRF → 可选精排
│   ├── generation.py               # 同来源有限历史、查询改写、上下文
│   ├── prompts.py                  # 数据/指令边界、资料不足与引用要求
│   └── citations.py                # 引用编号归一化、验证和快照构造
└── infrastructure/
    ├── database/
    │   ├── connection.py / models.py
    │   ├── repositories.py         # 资料、片段、任务持久化
    │   ├── rag_repository.py       # 索引版本、会话、消息、引用持久化
    │   ├── migrate.py              # 升级备份、事务化 schema 迁移
    │   └── migrations/
    │       ├── 001_initial.sql
    │       └── 002_research.sql
    ├── storage/local_files.py
    ├── tasks/local_runner.py       # 单进程锁、单工作线程、注入回调
    ├── vector/chroma.py            # 显式向量操作，不下载默认模型
    └── models/
        ├── settings.py             # 配置合并、密钥隔离、Embedding 配置标识
        ├── transport.py            # HTTP/超时、对外错误脱敏
        ├── embedding.py           # 数量、维度、数值校验
        ├── llm.py                  # 普通/流式 Chat Completions
        └── reranker.py             # 精排协议和结果索引校验
```

根目录还包括 `data`（运行数据，不提交）、`docs`（工程说明）、`samples`（公开测试材料）、`scripts`（启动/显式模型验证）。

## 数据库：schema v2，七张业务表

| 表 | 主要内容 |
|---|---|
| notebooks | 专题、固定本地归属、名称与时间 |
| sources | 文件信息、解析状态、索引状态、有效版本/模型配置/维度、错误 |
| chunks | 原文片段、稳定 ID、页码与字符位置 |
| jobs | parse/index 类型、目标配置/版本、状态；同来源仅一个活动任务 |
| conversations | 专题下的会话 |
| messages | user/assistant、请求键/指纹、来源列表、内容、状态、警告/错误 |
| citations | 回答对应编号、chunk/source ID、文件名、原文及位置、索引版本快照 |

`user_version` 记录迁移版本，不增加第八张业务表。v1 升级前保存 `.v1-backup-*` 本地备份；不修改旧迁移，不覆盖非空无版本数据库。会话与消息级外键、请求唯一约束和“每会话一个生成中回答”的部分唯一索引由数据库兜底。

引用的 chunk/source ID 是历史标识，不依赖当前片段仍然存在；原文快照随消息保存，防止重建后失去当时依据。

## 索引链路

```text
parsed 来源 → 手动请求 → 持久化 index job → 分批 Embedding（每批16）
 → Chroma upsert → 核对全部片段 ID → SQLite 原子切换 ready/有效版本
```

- 解析状态与索引状态独立；索引失败不破坏原文阅读。
- 配置标识包含 Embedding 地址、模型、显式维度、向量协议版本，不包含密钥。
- Chroma collection 按专题、配置标识、实际维度区分；记录按 source+revision 限定范围。
- 稳定向量 ID 为 revision+chunk_id；同配置失败重试复用 revision，覆盖写入避免重复。
- 全部成功才 ready。重建期间暂停该来源问答，成功后切换版本；失败保留旧记录但不继续当作 ready 使用。
- 旧版本向量暂保留，查询严格排除；目前没有自动清理旧版本的维护界面。
- 启动恢复时，中断 index 标记失败；排队任务仍可执行，配置改变则明确失败，不自动用新模型完成旧任务。

## 问答与引用链路

```text
校验会话/来源/索引 → 幂等保留问题与回答记录
 → 同来源有限历史（最近6条、每条最多1500字符）→ 必要时改写检索问题
 → 选定来源内向量与 BM25（各最多20）→ RRF → 可选精排
 → 最多6个证据、总计最多12000字符 → 编号 → 模型流式生成
 → 引用校验 → 事务保存回答和引用 → done
```

- 必须明确选 1～10 个来源；未就绪、不同专题或不同 Embedding 配置直接拒绝，不默默扩大或缩小范围。
- 切换来源时，历史消息若包含不在本轮范围内的来源，则不进入本轮模型上下文；同来源历史仅帮助指代，不作为事实证据。
- 向量查询预先使用 source+revision 过滤；返回 ID 再与 SQL 的允许片段集合核对。BM25 使用同一来源集合，不复用跨范围缓存。
- 生成与引用使用同一证据集合；引用版本绑定已验证的检索快照，而不是后续可能变化的来源元数据。
- `[S1]` 等标签只有属于本轮证据才可点击；有限归一化 `（S1）` 等明确标签，不猜测文件名或裸 `S1` 的含义。
- 无效编号取消链接并警告；没有有效引用也警告。编号正确不等于语义被核验，当前未实现自动事实核查。
- Reranker 失败降级至 RRF 并保存警告。LLM/Embedding/存储失败不退回无资料依据的普通回答。
- SSE 只有保存成功才发送 done；截断/错误不记为成功。断开时保留已接收内容并标记 interrupted，重启恢复运行中记录。

## 安全与部署边界

仅本机单进程，不支持多用户或公网。不同地址不自动继承另一个供应商 Key；客户端不读配置文件或 Key。模型客户端不执行网页内容指令、不访问链接，也没有联网搜索工具。必要片段、问题与限定历史会发送给所配置服务，原始密钥和旧版资料不会被自动上传。

提示词防护不是抵御所有提示注入的保证；本应用没有工具执行权限暴露给模型。索引重建、历史存储、异常恢复等细节见 research.md。
