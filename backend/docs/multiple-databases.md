# 数据源与日志库

主库 `res-nexus` 对应 `default`，日志库 `res-nexus-log` 对应 `logs`。先创建两个数据库并授权，应用不会创建数据库本身。数据库名含连字符，执行 SQL 时必须使用反引号引用。

```dotenv
DATABASE_NAME = res-nexus
DATASOURCES = {"logs":{"database":"res-nexus-log"}}
```

`database` 继承主库服务器、驱动及凭据。独立实例可提供 `async_url`，需要同步组件时提供 `sync_url`；URL 必须使用对应的异步/同步驱动。每个数据源可覆盖 `pool_size`、`max_overflow`、`pool_timeout`。配置通过环境变量或 env 文件加载，重启生效。`default` 禁止重复声明，`logs` 必须存在且不能指向主库。SQLite 应提供不同的数据库文件路径。

HTTP 接口使用 `Depends(get_db("name"))`，同请求同名依赖共享会话。保留 `db_getter` 作为主库依赖，`log_db_getter` 作为日志库依赖。认证、权限、系统配置、调度器存储固定走主库。

后台任务及非 HTTP 代码使用：

```python
from app.core.database import databases

async with databases.session("logs") as db:
    # 成功提交，异常回滚，退出关闭。不能跨任务共享 AsyncSession。
    ...
```

登录、操作、HTTP 调用日志（包括正文）、月表目录、清理和下载均使用日志库。日志模型不进入主库 metadata，不建立跨库用户外键。仪表盘分库查询后组合。各库事务独立，不能保证跨库原子提交；日志写入失败记录运行日志，不回退主库。

日志月表由原有版本化机制初始化和按月创建；应用用户需要日志库建表权限。主库 Alembic 不管理日志表。旧迁移历史不改写；新安装通过主库 metadata 自举并 stamp head，日志库单独初始化。升级旧安装前应先应用既有历史到拆分前的 head，再搬迁日志表；不要在拆分后的主库重放早期日志建表迁移。

额外外部数据源只提供连接与会话，不自动扫描模型、建表或执行迁移。文件运行日志继续由现有日志系统管理。

本次开发库搬迁为一次性数据库操作，不提供自动搬迁脚本或命令。目标表冲突时禁止覆盖，搬迁并核验后删除旧库。

日志月份统一登记在日志库 `sys_log_month(kind, month, version)`，联合主键为 `(kind, month)`；不再使用独立的审计和 HTTP 月份目录。实际日志月表结构不变。

金仓 PostgreSQL 兼容接入配置、限制和实机验收见 [kingbase.md](kingbase.md)，当前待实机验证。
