# 本地运行数据

首次启动后建立 app.sqlite3，保存 notebooks、sources、chunks、jobs 四张业务表；schema 版本为 SQLite user_version=1。

- uploads/<source-id>：原始文件，以服务端生成 ID 存储，没有原始文件名路径。
- uploads/.pending/：尚未登记的临时文件。
- .app.lock：单进程文件锁；只允许一个后端使用此目录。
- chroma/：预留目录，本轮不使用。

所有运行数据均被 Git 忽略。停止服务后备份整个目录，不单独删除原文件或数据库。使用 WORKBENCH_DATA_DIR 可指定独立目录；旧版 docs 和 chroma_db 不会迁入。
