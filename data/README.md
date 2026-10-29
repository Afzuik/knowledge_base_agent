# 本地运行数据

当前 schema v3：notebooks、sources、chunks、jobs、conversations、messages、citations、notes 八张业务表，版本保存在 SQLite user_version。

- app.sqlite3：业务数据、会话、笔记与引用快照。
- app.sqlite3.v1-backup-* / app.sqlite3.v2-backup-*：对应版本升级前的自动本地备份。
- uploads/<source-id>：原文件；uploads/.pending 为上传临时文件。
- chroma/：本地向量索引，区分专题、模型配置、维度与来源版本。
- .app.lock：只允许一个后端进程使用此目录。

全部运行数据被 Git 忽略。停止服务后备份整个目录；不能只备份 Chroma，也不能用旧版重建脚本删除这里。WORKBENCH_DATA_DIR 可指定独立目录。原始密钥不存入数据库。
