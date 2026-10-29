"""待实现：编排解析、切片、Embedding、索引及任务状态持久化；重试幂等。

调用 intelligence 的解析切分能力及 infrastructure 的数据库、向量和模型适配器。
完整成功后才设 source.status=ready；中间失败的数据不得用于问答。
状态：queued → parsing → indexing → ready / failed。
透传 owner/notebook/source/job ID；重启将中断任务标记可重试。
"""
