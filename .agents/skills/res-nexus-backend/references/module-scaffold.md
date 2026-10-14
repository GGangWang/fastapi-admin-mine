# 新建模块全流程

## 步骤

1. 建目录 `app/modules/<module>/<feature>/`（或 `app/plugin/module_xxx/`），放 5 个文件 + `plugin.toml`（见 SKILL.md 分层）
2. `model.py`：继承 `app/core/base_model.py` 的基础表模型（主键 `id`、`created_time`/`created_id`/`updated_time`/`updated_id`/`deleted_time` 等审计字段）
3. `schema.py`：`Create`（写入）、`Update`（全 Optional）、`Out`（继承 base_schema 的 `BaseSchema`，含审计字段）、`Query`（分页 + 模糊查询）
4. `crud.py`：`class XxxCRUD(CRUDBase[Xxx, XxxCreateSchema, XxxUpdateSchema])`；表查询走 `table=xxx_model`
5. `service.py`：`class XxxService(BaseService)`，构造函数 `(self, auth, db)`
6. `controller.py`：按 [controller-pattern](./controller-pattern.md) 写路由
7. **注册路由**：`app/api/v1/routers.py` 的 `DOMAIN_CONTROLLERS`（见下）
8. 建表/改表：生成 Alembic 迁移；菜单、按钮权限、字典等种子数据补进 `backend/sql/*.json`
9. **重启后端**

## 路由注册（唯一真源）

`app/api/v1/routers.py`：

```python
DOMAIN_CONTROLLERS = {
    "ai": AI_CONTROLLER,
    "monitor": MONITOR_CONTROLLER,
    "system": SYSTEM_CONTROLLER,
    "generator": GENERATOR_CONTROLLER,
    "xxx": XXX_CONTROLLER,          # ← 新模块加在这里
}

api_router = APIRouter()
for domain, controller in DOMAIN_CONTROLLERS.items():
    if controller is not None:
        api_router.include_router(controller, prefix=f"/{domain}")
```

- 每个 domain 的 controller 聚合文件 import 各 feature 的 `xxx_router` 并 re-export 成 `AI_CONTROLLER` 这种大写常量
- `APP_API_V1_PREFIX = "/api/v1"` 全局前缀

## 动态路由发现（app/core/discover.py）

- `discover_all_controllers()` 在**启动时**扫描 `app/modules/**` 与 `app/plugin/**` 每个模块（根目录有 `plugin.toml` 才算模块），把带 `__controller__` 标记的路由按 `plugin.toml` 的 `name` 前缀动态挂到 `api_router`
- **开发模式不重启 = 新模块不生效**：uvicorn reload 只按文件变化重载，动态发现只在进程启动时跑一遍；改了 `routers.py` 或新增模块目录后必须手动重启后端
- `app/plugin/**` 与 `app/modules/**` 同结构同机制（`plugin.toml` 的 `name` 决定挂载前缀与权限标识前缀）
- 权限标识前缀 `module_<插件name>:`，如 `module_ai:chat:query`

## 常见坑

| 现象 | 原因/处理 |
| --- | --- |
| 新模块接口 404 | 没注册进 `DOMAIN_CONTROLLERS`，或没重启（动态发现未执行） |
| 启动报路由重复 | 同一 `prefix+path` 被两个 controller 注册；查 `DOMAIN_CONTROLLERS` 与 plugin 前缀冲突 |
| 权限 403 | 权限标识三段式 `module:x:y` 与 `backend/sql/sys_menu.json` 按钮权限对不上 |
| 审计字段缺失 | model 没继承基础表模型；`BaseSchema` 已带审计字段，Out schema 别手写丢失 |
