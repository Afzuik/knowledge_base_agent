# 知识研究工作台

面向个人学习与研究的来源驱动 AI 工作台。当前交付 **资料入库链路**，尚未接入模型或问答。

## 已实现

- 创建、查询专题；名称去除首尾空格，1～100 字符，允许同名。
- 上传文本型 PDF、Markdown、TXT；原文件本地保存，默认单文件 20 MiB。
- 后台串行解析与切片，展示等待、解析中、已解析、失败及任务历史。
- 预览原文片段、PDF 页码或文本字符位置；分页获取片段。
- 同专题按 SHA256 去重；失败重试、重启恢复、临时文件/孤立文件清理。
- SQLite 持久化四张业务表；数据库版本通过 `PRAGMA user_version` 管理。

**已解析不等于可问答。** 当前所有资料都显示“未索引”；不调用 LLM、Embedding 或 Reranker，也不生成向量。注册登录、多用户隔离、笔记、问答和引用生成尚未实现。

## 四层架构

| 层 | 代码位置 | 职责 |
|---|---|---|
| ① 界面层 | `frontend/src/` | 专题、上传、状态轮询、片段预览 |
| ② 应用层 | `backend/app/application/`，HTTP 入口 `backend/app/api/` | 用例、归属校验、导入编排、错误与重试规则 |
| ③ AI 处理层 | `backend/app/intelligence/` | 当前只做本地文本解析和切片，不调用 AI 模型 |
| ④ 数据与外部服务层 | `backend/app/infrastructure/` | SQLite、原文件、后台执行；模型和向量模块仍为占位 |

详见 [架构文档](docs/architecture.md)、[接口与运行说明](docs/ingestion.md)、[验收记录](docs/testing.md)。

## 安装与启动

支持 macOS / Linux；Python 3.12、uv、Node.js（`^20.19.0 || >=22.12.0`）、npm。本轮进程互斥使用 POSIX 文件锁，**Windows 暂未支持或验证**。

在仓库根目录执行：

```bash
(cd backend && uv sync --frozen)
(cd frontend && npm ci && npm run build)
bash scripts/run_local.sh
```

打开 <http://127.0.0.1:8765>。首次启动会应用版本 1 的建表迁移；导入模块本身不会建库。Ctrl+C 正常关闭时等待当前任务完成。

无需 API Key，也不会读取旧 `.env`。原版与 `learning-notes` 均在仓库外，不会自动导入。

### 演示

1. 创建“Agent 学习”专题。
2. 上传 `samples/agent-learning.md` 或 `samples/reading-note.txt`。
3. 等待“已解析”，点击资料核对片段。
4. 重复上传同一文件，观察去重提示。
5. 刷新或停止服务后重新启动，专题、资料与片段仍然存在。

文本需要 UTF-8；扫描件无文本、损坏或加密 PDF 将显示明确失败原因。重试不会修复损坏内容，需要恢复原文件或上传修正后的新资料。

### 开发与独立数据目录

运行后端的同时，在另一个终端执行 `(cd frontend && npm run dev)`，访问 <http://127.0.0.1:5173>。

可通过非敏感环境变量指定独立绝对数据目录，例如：

```bash
WORKBENCH_DATA_DIR="$PWD/reports/local-demo-data" bash scripts/run_local.sh
```

仅允许一个后端进程使用同一数据目录，不要添加 `--workers`。服务只监听本机，不要暴露到公网。

## 测试

```bash
(cd backend && .venv/bin/python -m pytest -q)
(cd frontend && npm run build)
bash -n scripts/run_local.sh
```

自动化测试全部使用临时目录，不写正式 `data`，也不调用模型。健康接口标识 `ingestion_ready: true`、`qa_ready: false`、`business_ready: false`：资料处理能力已接入，但完整研究流程尚未完成。这不是持续磁盘健康检测。

## 数据与限制

- SQLite：`data/app.sqlite3`；原文件：`data/uploads/<source-id>`；向量目录当前不使用。
- 数据、原文件、日志、密钥、虚拟环境和构建产物均不提交 Git。
- 删除整个数据目录不可当成正常的恢复方式。备份/恢复方法见运行说明。
- 原文件按内容不可变；处理前核验大小与 SHA256，检测手工修改。
- 这仍是本机单用户应用；固定身份不是认证，专题范围校验不是多租户安全证明。
- 默认限制 200 页 PDF、200 万字符、单页解压内容 10 MiB；不是隔离恶意 PDF 的沙箱。不要导入不可信的攻击性文件。
- 不支持 OCR、URL 抓取、文件替换、删除专题或资料；本轮只完成已确认的创建与导入链路。
