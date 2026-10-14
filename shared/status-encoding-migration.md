# 启停编码切换（2026-10-14）

启停语义统一为 EnableStatus.ENABLED=1、DISABLED=0；BusinessStatus 正常=1、停用=0。不新增删除值，is_deleted 与删除审计字段保持原机制。

公告独立使用 NoticeStatus：0草稿、1已发布、2已归档，字典类型 sys_notice_status。公告列表、表单及回显使用发布字典，普通用户仅获取已发布公告。批量操作为发布/转为草稿，归档在编辑中设置。

## 迁移与回退

正式修订：20261014_enable_status，上一个修订为20261013_dict_tree。仅迁移修订内列出的13张有效状态表；同时更新服务器默认值。包含软删除行，不改其删除标记。工单、公告、版本、日志、任务执行及传输状态不转换；字典项业务编码只允许转换指定启停类型，性别/布尔等编码保持不变。

本机 MySQL、Redis 使用现有 Docker 容器：docker start mysql redis。

后端停服后，在 backend 目录执行：

```powershell
uv run python -m app.scripts.status_encoding_backup backup logs/status-before.json
uv run alembic upgrade head
uv run python -m app.scripts.status_encoding_backup verify logs/status-before.json
uv run python -m app.scripts.status_encoding_clear_cache
```

备份只记录主键、状态与删除标记，路径必须不存在以避免覆盖。转换前逐表检查，不接受NULL或非0/1数据。版本由Alembic管理，重复upgrade不再次翻转。回退时停服，执行 alembic downgrade 20261013_dict_tree，并同步恢复旧版本前后端、清理缓存；不得只回退代码或只恢复数据库。MySQL DDL会隐式提交，默认值DDL在数据DML前执行；失败应先核对备份和版本，不盲目重跑。

前端字典缓存版本升级为V4，配置缓存升级为V2，切换后需要重新登录。生产产物同步 backend/dist 与 docker/nginx/web/dist。

## 本次验证

实际数据库已备份到 backend/logs/status-encoding-20261014-before.json（忽略提交）。13张表共213条记录转换完成，逐条语义、删除标记与独立业务状态对比通过。临时数据库升级/降级、异常值拦截和默认值演练通过；后端123项测试、前端9项字典测试通过，生产构建通过。演示页原有3处TS2352单独保留。
