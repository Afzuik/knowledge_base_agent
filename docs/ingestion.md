# 资料入库接口与运行说明

## HTTP 接口

前缀 `/api`。所有身份由后端固定提供，不接受调用方自定义 owner。

| 方法 | 路径 | 含义 |
|---|---|---|
| GET | `/health` | 进程/当前能力标识、大小限制；不持续检测磁盘 |
| POST | `/notebooks` | JSON `{"name":"Agent 学习"}`；201 |
| GET | `/notebooks` | 当前本地身份的专题列表 |
| GET | `/notebooks/{nid}` | 专题详情；不存在或非当前身份返回 404 |
| POST | `/notebooks/{nid}/sources` | multipart 字段 `file`；新资料 202，重复资料 200 |
| GET | `/notebooks/{nid}/sources` | 资料列表 |
| GET | `/notebooks/{nid}/sources/{sid}` | `source` 与 `jobs`，任务历史倒序 |
| GET | `/notebooks/{nid}/sources/{sid}/chunks` | 仅 parsed 可读，其他状态 409；offset≥0、1≤limit≤100 |
| POST | `/notebooks/{nid}/sources/{sid}/retry` | 失败来源且原文件存在时 202；非失败/已重试/原文缺失为 409 |

上传响应为 `{"source": {...}, "duplicate": false}`。parsed 不代表已索引；每条来源包含 `index_status（未建立索引时为 not_indexed）`。存储路径与 owner 不出现在响应中。

输入错误返回 422/415；大体积请求早期返回 413；数据库或文件系统故障返回 503；未完成解析读取片段返回 409。应用错误使用 `code`、`message`；Pydantic 校验错误使用标准 `detail`。异常消息不暴露内部路径或密钥。

## 上传与解析规则

- 同专题、相同 SHA256 只登记一次；原文件名不同也去重。不同专题可以分别上传相同内容。
- 同名但不同内容视为新来源，不替换旧内容。不支持原文件原地更新。
- 默认单文件 20 MiB；Content-Length 超过文件上限+64 KiB 的上传请求提前拒绝，文件存储仍按实际字节验证。
- 未声明 Content-Length 的 multipart 请求可能先由框架落临时文件，当前不是面向公网的完整流量/磁盘配额控制。
- PDF：最多 200 页，提取后最多 200 万字符，解压页流最多 10 MiB；这些不是针对恶意文件的硬资源沙箱。解析器线程没有强制终止超时，恶意或极复杂 PDF 仍可能拖慢当前任务。
- TXT/MD：UTF-8 或 UTF-8 BOM；拒绝无文本、非法编码和异常控制字符。Markdown 作为原文显示，不执行 HTML。
- 默认片段 800 字符、重叠 100；PDF 不跨页切片，页码从 1 开始。
- 解析阶段只保存文本和位置，不调用模型；后续手动索引与问答见 research.md。

## 后台执行

一个后端进程、一个后台线程，约每 250ms 从 SQLite 领取任务。HTTP 同步业务在框架工作线程中执行，后台解析不直接占用事件循环。没有 Redis/Celery，没有分布式执行承诺。

正常停止服务会等待当前任务完成；强制终止后，在下一次启动将 running/parsing 标为 failed/interrupted，可手动重试；queued 仍会继续领取。

## 数据与备份

默认目录为仓库 `data/`；`WORKBENCH_DATA_DIR` 可指定独立数据目录。一个目录不能由多个后端进程同时打开。测试使用临时目录或被忽略的 `reports/` 下独立数据目录，不会将测试资料放入默认库。

备份步骤：

1. 正常停止服务，确认退出。
2. 复制整个数据目录（数据库与 uploads 必须一起保留）。
3. 恢复到一个新的独立目录，通过 `WORKBENCH_DATA_DIR` 启动验证。
4. 不要仅备份 Chroma，不要用旧版 `rebuild_db.py`，不要删除整个库来处理失败任务。

本次修改前的源码、SHA256 和后续验证日志保存在本地 `reports/ingestion/`。Git 可以恢复代码，但不会恢复被忽略的数据。回退到前一版工程骨架不会显示新资料；需要保留本版数据库和原文件，不要向未知/旧 schema 强行写入。

## 人工故障定位

- `invalid_encoding`：将文本转为 UTF-8，作为新资料上传。
- `no_text`：可能是扫描 PDF、空白页或空白文本，本版无 OCR。
- `invalid_pdf` / `encrypted_pdf`：修复或解密后上传新资料。
- `file_changed`：原文件哈希/大小变动；恢复原文件或上传新版本。
- `missing_file`：恢复相应原文件后重试；路径由资料 ID 决定。
- `interrupted`：上次处理被中断，可重试。
- `processing_error`：解析或片段保存异常，查看服务日志并确认磁盘/数据库后重试。
