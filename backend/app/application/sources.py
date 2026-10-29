"""待实现：资料登记、上传规则、任务创建、状态查询及资源范围检查。

由 application.ingestion 编排解析与索引；具体文件访问交给
infrastructure.storage.local_files，执行机制交给 infrastructure.tasks.local_runner。
本模块决定允许处理什么资料，不承担文件系统和队列实现。
"""
