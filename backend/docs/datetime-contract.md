# 前后端时间契约

所有管理端日期时间字段使用北京时间 `Asia/Shanghai`，格式严格为
`YYYY-MM-DD HH:mm:ss`。无时区字符串表示北京时间；接口不接受 ISO 8601
（`T`、`Z`、偏移量）、时间戳或小数秒。纯日期、纯时间沿用原格式。

普通数据库时间字段保持 UTC。`DateTimeStr` 在校验前解析北京时间入参为 UTC，
Python `model_dump()` 保留 UTC datetime 用于存储和查询；JSON 序列化和
`SuccessResponse` 的裸 datetime 编码统一转换回北京时间。不要提前格式化 UTC
datetime，也不要将展示字符串重新当 UTC。导出 Excel 使用相同规则。

前端 API 时间字符串是北京时间日历值，直接显示或调用 `utils/dateTime.ts`。
表单调用 `dateTimeFormValue` 校验后原样提交，不调用 `toISOString()`。
Date/Unix 毫秒等第三方来源的绝对时刻通过 `formatDateTime` 显式转北京时间。
浏览器处于其他时区时，系统仍显示北京时间。日期选择器的快捷范围采用北京时间。

## 已知特殊存储

| 字段/来源 | 原语义 | 适配 |
| --- | --- | --- |
| 基础 created_time/updated_time/deleted_time、登录/操作日志、传输任务 | UTC | 无时区 ORM 值按 UTC；响应转北京时间 |
| HTTP started_at | 北京时间，无时区 | 保留原数据；明确按北京时间输出和筛选 |
| 用户 last_login、会话 login_time | 历史服务器本地时间，当前部署为北京时间 | 保留旧值；显式北京时间写入和输出，不按普通审计时间加 8 小时 |
| 示例 datetime_val | 历史表单北京时间，无时区 | 保留该业务字段原存储语义；输出使用明确适配 |
| 本地文件、SFTP 时间戳 | Unix 时刻 | 带 UTC 解析，统一输出 |
| FTP MLSD modify、OBS lastModified、OSS | 来源协议 UTC | 明确附加/归一化 UTC 后输出 |
| 调度日期与起止时间 | 北京时间 | 严格解析，使用带 Asia/Shanghai 的调度时间 |

不迁移或统一偏移历史数据。若过去的服务器并非北京时间，last_login 的原始语义须另行
核验，禁止猜测后批量修正。新模块使用 DateTimeStr；生成模板沿用该类型。
内部会话缓存的 created_at、JWT、安全令牌、第三方协议的原始格式保持不变；旧缓存的
login_time 只在输出边界兼容解析，不能以此放宽公共接口入参。

## 发布

前后端同时发布。原先提交 ISO 时间的调用方必须改为北京时间统一格式，三类日志亦然。
重新构建前端并同步 backend/dist 与 docker/nginx/web/dist，重启后端。
使用 UTC、Asia/Shanghai、America/New_York 环境验证显示、编辑回显和范围筛选一致。
