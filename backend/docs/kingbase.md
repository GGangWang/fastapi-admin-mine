# 人大金仓接入（PostgreSQL 兼容模式，待实机验证）

新增逻辑类型 `kingbase`，使用 SQLAlchemy PostgreSQL 方言及 psycopg 3 同步/异步驱动。当前没有金仓测试实例，离线测试不能证明 V8/V9 实机兼容；这不是官方 ksycopg2 方言，也不支持 Oracle 兼容模式。

## 安装与主库配置

```powershell
uv sync --extra kingbase
```

参考 `env/.env.kingbase.example` 配置环境：

```dotenv
DATABASE_TYPE=kingbase
DATABASE_HOST=your-server
DATABASE_PORT=54321
DATABASE_USER=your-user
DATABASE_PASSWORD=your-password
DATABASE_NAME=res-nexus
DATASOURCES={"logs":{"database":"res-nexus-log"}}
```

主库及日志库需提前创建并授权。端口必须按实例配置；54321 只是示例。同步和异步 URL 均为 `postgresql+psycopg://...`，由 SQLAlchemy 根据引擎类型选择实现。仅提供数据源数据库名时继承主库服务器、凭据和驱动。没有修改当前开发 MySQL 配置或搬迁其数据。

MySQL 主库可以继续使用原配置，增加金仓业务数据源：

```dotenv
DATABASE_TYPE=mysql
DATASOURCES={"logs":{"database":"res-nexus-log"},"business":{"async_url":"postgresql+psycopg://user:password@host:54321/business","sync_url":"postgresql+psycopg://user:password@host:54321/business"}}
```

显式 URL 中用户名和密码需 URL 编码；配置字段生成的金仓 URL 自动处理特殊字符。连接失败不会回退到 MySQL/SQLite。默认仍使用 `public` schema。AI 会话使用 PostgreSQL 后端。Windows 服务、Alembic 和内置日志清理会为 psycopg 选择 Selector 事件循环；自行调用 `asyncio.run` 的脚本应使用 `asyncio.Runner(loop_factory=asyncio.SelectorEventLoop)`。

## 实例能力要求与限制

目标实例需接受 PostgreSQL 协议，提供标准方言所需的服务器版本信息、事务与反射功能。不会伪造版本字符串，也不会绕过 SQLAlchemy 初始化；服务器版本响应不能被 PostgreSQL 方言识别时，连接会失败，需依据真实实例评估专用方言。

需要验证：`pg_catalog`（pg_class/pg_namespace/pg_description 等）、information_schema、ILIKE、COMMENT、自增序列及 RETURNING、ON CONFLICT、JSON/JSONB、布尔及时间类型、`pg_advisory_xact_lock`、`convert_to`、`octet_length`。AI 表可能额外使用 PostgreSQL JSONB 和聚合功能。缺少这些能力时不能认定整个框架兼容。

主库模型、Alembic、独立日志库、统一 `sys_log_month`、动态月表以及同步代码生成器均复用 PostgreSQL 路径。额外数据源不自动建表或执行迁移。保持当前日志库隔离和原 API；不改写历史迁移，不提供 MySQL 到金仓的数据迁移。

## Docker 连接外部金仓

```sh
docker build --build-arg DB=kingbase -f docker/backend/Dockerfile -t res-nexus-backend:kingbase .
docker run --env-file /secure/res-nexus.env -p 8001:8001 res-nexus-backend:kingbase
```

环境文件需包含生产密钥、主库、日志库和可达 Redis 等配置。现有 Compose 的数据库服务是 MySQL，不应将其直接当作金仓部署；本次不提供金仓镜像。`all-db` 安装方式也包含所需驱动。

## 测试与实机验收

离线：`uv run --extra kingbase pytest tests/test_kingbase.py tests/test_datasources.py`。这些测试验证配置/引擎选择、DDL 编译、生成器、AI 选择、缺驱动提示与 Windows 事件循环，不会连接金仓。

实机探测需要两个专用数据库，名称必须以 `_test` 结尾，并显式启用：

```powershell
$env:KINGBASE_RUN_INTEGRATION='1'
$env:KINGBASE_TEST_URL='postgresql+psycopg://user:password@host:54321/res_nexus_test'
$env:KINGBASE_TEST_LOG_URL='postgresql+psycopg://user:password@host:54321/res_nexus_log_test'
uv run --extra kingbase pytest tests/test_kingbase_integration.py -q
```

未启用时跳过。探测在两个测试库中创建随机私有 schema，结束后仅删除这些 schema；不读取开发库配置作为目标。覆盖同步/异步连接、模型 DDL、Inspector、基本 Alembic DDL、系统目录/函数、CRUD/回滚、日志目录和正文、AI 建表。失败只输出阶段和异常类型，不输出连接凭据。可执行 `uv run --extra kingbase python tests/kingbase_probe.py` 查看阶段。

实机全面验收仍需在独立测试部署完成：空库启动及种子数据、完整升级流程、登录成功/失败、权限、主库与日志库隔离、列表/详情/导出/下载、跨月并发创建、保留期清理、仪表盘、生成器表字段及 SQL 导入、AI 会话读写、调度器存储与关闭释放。记录金仓完整版本、兼容模式和操作系统；通过前状态始终为“未实测”。
