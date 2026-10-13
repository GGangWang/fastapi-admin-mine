---
name: fastapiadmin-backend
description: "Use for ResNexus backend (backend/, FastAPI + SQLAlchemy async + Redis + Alembic + uv) code writing, module creation, route/permission wiring, table migrations, env config. Invoke before writing or changing backend code, creating business modules, or debugging route/permission issues. Keywords: FastAPI, controller, service, crud, model, schema, APIRouter, AuthPermission, OperationLogRoute, SuccessResponse, CustomException, Alembic, uv, plugin.toml, app/modules, app/plugin, routers.py."
argument-hint: "module name, table name, interface path, or issue description"
---

# ResNexus 后端技能

适用 `backend/`。管理端前端改动看 `fastapiadmin-web`；代码生成看 `fastapiadmin-generator`；部署看 `fastapiadmin-deploy`。

## 何时使用

- 新建/修改业务模块（`app/modules/<module>/<feature>/` 或 `app/plugin/module_xxx/`）
- 接口、权限标识、响应结构 增改；表结构迁移（Alembic）
- 配置/修改 `env`（数据库切换、CORS、安全密钥、调度器开关等）
- 排障：启动失败、路由冲突、404、权限错误

## 目录与分层（自上而下）

```
app/modules/<module>/<feature>/
├── controller.py   # 路由层：APIRouter + deps，不写业务逻辑
├── service.py      # 业务层：XxxService(auth, db)，可含 Redis 缓存
├── crud.py         # 数据层：继承 CRUDBase
├── model.py        # SQLAlchemy ORM（基础表见 app/core/base_model.py）
└── schema.py       # Pydantic：Create/Update/Out/Query 四组
```

- 模块根目录放 `plugin.toml`（name/title/version/description）
- 常规业务放 `app/modules/`；可插拔/示例性质放 `app/plugin/`（同结构、动态发现，见 [module-scaffold](./references/module-scaffold.md)）
- 路由必须注册进 `app/api/v1/routers.py` 的 `DOMAIN_CONTROLLERS`（路由唯一真源）
- 基建全在 `app/core/`：`base_crud.py` / `base_schema.py` / `base_model.py` / `dependencies.py` / `exceptions.py` / `redis_crud.py` / `logger.py`（loguru，占位符是 `{}` 不是 `%s`）
- 响应统一 `SuccessResponse(data=..., msg=...)` + `response_model=ResponseSchema[T]`；业务错误抛 `CustomException`
- 权限统一 `Security(AuthPermission(["module:resource:operation"]))`；标识格式 `module_<模块>:<资源>:<操作>`，与前端 `v-hasPerm` 一致

## 核心规则

1. controller 只做三件事：参数校验（`Annotated` + FastAPI deps）、调 service、包响应——不写 db/redis 逻辑
2. service 构造函数收 `(auth, db)`；`redis` 作为方法参数按需传入（不是每个端点都要）
3. CRUD 继承 `CRUDBase[Model, CreateSchema, UpdateSchema]`；通用查询/分页/删除已封装，不写裸 SQL
4. 改 model 后必须生成并应用 Alembic 迁移；菜单/角色/字典/参数等种子数据放 `backend/sql/*.json`
5. **新增/修改模块后必须重启后端**：开发 reload 只按文件变化重载，动态路由发现（`app/core/discover.py`）只在启动时执行，不重启则新模块静默不生效（完整坑见 [module-scaffold](./references/module-scaffold.md)）
6. 缓存模式：create/update/delete 后写缓存；批量操作按 key 分组、每组只刷一次；刷新失败记日志后重抛（见 [controller-pattern](./references/controller-pattern.md)）

## 验证

- 测试：`uv run pytest`（conftest 建临时库并灌种子数据）
- 开发启动：`uv run main.py run --env=dev`；Swagger `http://localhost:8001/docs`
- 健康检查：`GET /api/v1/monitor/health/check`（含 `cors_origins_configured` / `code_exec_enabled` 生效字段）

## 引用

- [controller-pattern.md](./references/controller-pattern.md) — controller 完整样例（dict 模块）与常见端点模式（分页/optionselect/批量删除/状态/导出）
- [module-scaffold.md](./references/module-scaffold.md) — 新建模块全流程、路由注册、动态路由发现与"必须重启"坑
- [config-and-env.md](./references/config-and-env.md) — env 配置、生产必备安全项、数据库切换
