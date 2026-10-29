"""待实现：资料登记、任务创建、状态查询及原文访问范围检查。"""

"""待实现：按服务端生成的 source ID 存储文件，校验格式、大小和路径。

根目录固定为 data/uploads；不得直接使用用户文件名构造存储路径。
"""

"""待实现：有限并发导入，透传 owner/notebook/source/job ID。

状态：queued → parsing → indexing → ready / failed。
重启将中断任务标记可重试；每个任务使用独立数据库 session。
"""
