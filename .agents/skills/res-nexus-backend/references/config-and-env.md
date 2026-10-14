# 配置与环境（backend/env）

## 加载机制

- `app/config/setting.py`（pydantic Settings）统一读取，模板见 `backend/env/.env.example`
- `--env=dev|prod` 决定读 `env/.env.dev` 还是 `env/.env.prod`（`ENV_PATH = Path(__file__).parents[2] / "env" / f".env.{env}"`）
- docker 场景：镜像内 `.env.prod` 只是兜底，真实地址/密码由 compose 运行时注入（见 `res-nexus-deploy` 技能）

## 数据库切换

`DATABASE_DRIVER=mysql` 等值切换 `mysql / postgresql / sqlite`（对应 async 驱动 URL）。切换后注意：
- 迁移历史按驱动分目录；换驱动 = 换一套迁移库
- 种子数据 JSON（`backend/sql/*.json`）需在对应库上重灌

## 生产必备安全项（.env.prod）

| 变量 | 要求 |
| --- | --- |
| `SECRET_KEY` | 必填，`openssl rand -hex 32` 生成；缺失直接启动失败 |
| `PROD_CORS_ORIGINS` | 默认**空=拒绝所有跨域**；线上必须显式配置，健康检查有 `cors_origins_configured` 字段可核对 |
| `SCHEDULER_ALLOW_CODE_EXEC` | 默认 false；开启后 APScheduler 定时任务可执行代码，生产保持 false |
| `DEMO_ENABLE` | 演示模式开关；compose 默认 true（线上当前为演示模式，需要写入要设 false） |
| `DATA_ENCRYPTION_KEY` / `DATA_ENCRYPTION_OLD_KEYS` | 字段加密密钥，轮换时旧 key 放 OLD_KEYS |
| `FORWARDED_ALLOW_IPS` | 只信 app 网络子网（如 `10.255.178.0/24`），勿用 `*`（客户端可伪造 X-Forwarded-For 绕过登录限流/来源 IP） |
| `ALLOW_LOCALHOST_HOSTS` | 建议 false（Host 白名单收窄到生产域名；容器健康检查已改为发正确 Host） |
| `OAUTH_ALLOWED_HOSTS` | **JSON 数组**字面量（字段是 `list[str]`），逗号字符串会在启动期解析失败 |
| `CORS_STRICT_STARTUP` | 启动期 CORS 严格校验 |

## 其他常用项

- `LOGGER_LEVEL`：默认 INFO；日志文件 `backend/logs/res-nexus.log`（loguru，占位符 `{}`）
- `DEBUG`：默认 False，生产保持关闭
- `DATABASE_HOST/REDIS_HOST`：docker 内用容器服务名 `mysql` / `redis`
- `APP_SECRET_KEY` 等敏感项不入库不入镜像（deploy-artifacts 构建时会擦除）

## 排障

| 现象 | 检查点 |
| --- | --- |
| 启动 SettingsError | 必填项缺失或 JSON 类字段（`OAUTH_ALLOWED_HOSTS` 等）格式错误 |
| 接口跨域 4xx/被拒 | `PROD_CORS_ORIGINS` 为空或域名不匹配；看健康检查 `cors_origins_configured` |
| Host 400 | `ALLOWED_HOSTS` 与请求 Host 不匹配（TrustedHostMiddleware 开启） |

## 本地开发依赖

本机 MySQL 和 Redis 通过 Docker 运行，现有容器名分别为 `mysql` 和 `redis`。本地连接拒绝时先检查容器状态，使用 `docker start mysql redis` 启动；不要尝试启动 Windows MySQL/Redis 服务或新建替代容器。
