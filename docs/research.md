# 索引、问答、引用：接口与运行说明

## 模型配置与验证

本轮最终采用：

- LLM：DeepSeek 官方 `deepseek-flash`，`https://api.deepseek.com`，独立 DeepSeek Key。
- Embedding：SiliconFlow `Qwen/Qwen3-Embedding-8B`，显式 `dimensions=4096`。
- Reranker：SiliconFlow `Qwen/Qwen3-Reranker-8B`。

配置在被忽略的 `backend/.env`，示例见 `.env.example`。可通过 `WORKBENCH_MODEL_ENV` 引用已有本地配置，保存路径而非复制旧密钥。不要把 Key 发到聊天、写入前端或提交到 Git。

DeepSeek 的 `deepseek-flash` 不是 SiliconFlow 的模型 ID，不能只换 model 名而保留 SiliconFlow 地址。配置不同地址但未提供对应 Key 时，应用不会转发原供应商的 Key。独立配置 `LLM_BASE_URL/LLM_API_KEY`、`EMBEDDING_BASE_URL/EMBEDDING_API_KEY`、`RERANKER_BASE_URL/RERANKER_API_KEY`。

`LLM_ENABLE_THINKING=false` 在 DeepSeek 官方转换为 `thinking: {type: disabled}`；兼容的 SiliconFlow 服务使用 `enable_thinking`。应用不向浏览器输出推理内部字段，只处理最终回答文本。

官方协议参考：[DeepSeek 首次调用](https://api-docs.deepseek.com/)、[SiliconFlow Embedding](https://api-docs.siliconflow.cn/docs/api/embeddings-post)、[SiliconFlow Reranker](https://api-docs.siliconflow.cn/docs/api/rerank-post)。本实现为文本输入与 float 向量，不启用图片/视频或自动截断。

`MODEL_TRUST_ENV=false` 默认不继承进程的代理变量，避免错误的本地代理干扰；需要代理时显式设为 true。所有配置启动时读取，修改后重启。

显式运行 `backend/.venv/bin/python scripts/verify_models.py` 验证普通/流式 LLM、Embedding、Reranker。该命令会产生少量实际 API 消费。健康接口只报告配置存在，不持续付费探测服务或查询余额。

## 新增 API

所有路径前缀 `/api`，身份由服务端提供。

| 方法 | 路径 | 请求 / 返回 |
|---|---|---|
| POST | `/notebooks/{nid}/sources/{sid}/index` | JSON `{"force":false}`；202，已就绪/活动任务冲突为409；force重建 |
| GET | `/notebooks/{nid}/sources` | 增加 index_status/profile/revision/dimension/error/compatible |
| GET | `/notebooks/{nid}/sources/{sid}` | 资料详情与 parse/index 任务历史 |
| POST | `/notebooks/{nid}/conversations` | `{"title":"研究对话"}`；201 |
| GET | `/notebooks/{nid}/conversations` | 会话列表 |
| GET | `/notebooks/{nid}/conversations/{cid}/messages` | 消息、来源范围、状态、警告、引用快照 |
| POST | `/notebooks/{nid}/conversations/{cid}/messages` | question、source_ids、request_key；返回 SSE |

question 为 1～2000 字符；source_ids 为 1～10 项；request_key 为 8～128 位字母、数字、下划线或连字符。客户端不能指定 owner。引用原文随消息返回，不开放任意文件路径接口。

### SSE

- start：message_id。
- status：retrieving/generating，真实阶段而非虚构百分比。
- delta：文本片段。
- done：已保存的最终消息与引用。
- error：失败消息、部分内容和错误说明。

前端用 POST fetch 读取 SSE，不需要 WebSocket。流中编号暂按文本显示，done 中的已验证映射到达后才变为链接。

### 幂等与中断

同一会话、同一 request_key、同一问题和来源集合：已结束请求直接重放，不再次调用模型；进行中请求返回409。换问题或来源复用 key 返回409。同会话不能同时生成两个回答。

“停止生成”取消客户端连接；服务端在安全的迭代边界标记 interrupted 并保存部分文本。已发送到供应商的请求不能保证立刻取消计费，等待网络读取超时的调用可能延迟结束；UI 会轮询遗留 running 消息。

断流、长度截断、空回答和数据库保存失败都不会伪装为 done。若存储故障使失败状态本身无法保存，需恢复存储并重启，让启动恢复处理运行中记录。

## 索引状态与模型变更

`not_indexed → queued → indexing → ready / failed`，独立于解析状态。换 Embedding 地址、模型或显式维度后 index_compatible=false，重新建立索引才可选择问答。即使同名模型的返回维度突然改变，问答也会拒绝混用，需重建。

供应商同名同维度的内部模型权重更新无法仅靠该标识自动检测；需要人工判断是否重建。没有宣传为完整的模型版本追踪。

重建期间该来源暂停问答；旧向量不会被用于新版本，但暂保留在磁盘。旧版 Chroma collection 不会迁入新版。

## 数据升级、备份与恢复

历史迁移002（v2）在 v1 上添加索引字段、任务类型、conversations/messages/citations。迁移前自动备份 v1 数据库，不覆盖原文件。当前新库依次应用001、002、003（v3 新增 notes）。不要修改已应用的迁移文件。

完整备份仍需停止服务后复制整个 data 目录，包括 SQLite、uploads、chroma。只回退代码不能回退 schema；如果回退到 v1 代码，使用升级前备份与对应原文件的额外副本，不要让旧代码写 v2 库。引用快照存于 SQLite，重建不会重写已保存回答。

## 限制

- 没有联网搜索、认证、多用户隔离、并行工作进程。
- 无自动令牌成本预算或调用次数配额；建立索引和提问会产生实际费用。
- 切片仍为字符级规则，未实现复杂表格/版面理解；不保证召回所有相关证据。
- 当前不自动回收旧索引版本；持续大量重建需要后续维护功能。
- 提示词/引用标记验证不是事实核查，重要结论仍需人工阅读原文。
