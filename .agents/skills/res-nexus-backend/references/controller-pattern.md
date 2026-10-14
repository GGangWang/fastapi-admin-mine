# Controller 分层模式（dict 模块为样例）

参考文件：`backend/app/modules/system/dict/controller.py`。

## 结构

```python
from fastapi import APIRouter, APIRouter as _APIRouter  # 实际按需导入
from fastapi import Depends as _Depends, Path as _Path, Body as _Body, Query as _Query
from app.api.v1 import deps          # AuthPermission / AuthPermissionMixin / AuthUser
from app.modules.dict.schema import DictTypeCreateSchema, ...
from app.modules.dict.service import DictService

dict_router = APIRouter(route_class=OperationLogRoute)   # 自动操作日志
dict_type_router = dict_router


@dict_type_router.get(
    "/type/list",
    dependencies=[_Depends(AuthPermission(["module_dict:dict_type:query"]))],
    response_model=ResponseSchema[PageSchema[DictTypeOutSchema]],
    summary="字典类型列表",
    description="字典类型列表（分页）",
)
async def dict_type_list_controller(
    auth: AuthUser = _Depends(AuthPermissionMixin()),
    query: Annotated[DictTypeQuerySchema, _Query()] = None,
    db=Depends(auth.db),
):
    service = DictService(auth, db)
    page_data = await service.get_dict_type_list(query)
    return SuccessResponse(data=page_data, msg="字典类型列表（分页）")
```

要点：
- 模块级 `xxx_router = APIRouter(route_class=OperationLogRoute)`；子路由用同一实例（如 `dict_type_router = dict_router`）
- 端点函数命名 `xxx_<动作>_controller`，与 summary 对应
- 权限：路由级 `dependencies=[Depends(AuthPermission([...]))]`（整路由生效）；user 参数用 `AuthPermissionMixin()`（只校验登录）
- 分页参数通过 `Annotated[QuerySchema, Query()]` 传 schema 对象，不是散参
- `db=Depends(auth.db)` 是约定写法（session 与 auth 事务绑定）

## 常见端点模式

| 模式 | 写法 |
| --- | --- |
| 分页列表 | `response_model=ResponseSchema[PageSchema[Out]]`，service 返回 `PageResult` |
| 下拉数据 | `/xxx/optionselect`，`response_model=ResponseSchema[list[OptionSchema]]` |
| 详情 | `Path(id: int, ge=1)`，404 走 service 内抛 `CustomException` |
| 创建 | `Annotated[CreateSchema, Body(embed=True)]` |
| 更新 | `PUT /xxx/update/{id}` + `Annotated[UpdateSchema, Body(embed=True)]` |
| 删除 | `DELETE /xxx/delete`，`Annotated[list[int], Body(description="ID 列表")]` |
| 状态批量 | `PATCH /xxx/status/batch`，`Annotated[BatchDictTypeSchema, Body(embed=True)]`（ids + status） |
| 导出 | `POST /xxx/export`，`return await service.export_...()` 直接返回 `StreamingResponse`，不包 SuccessResponse |

## Service 缓存模式（字典类）

```python
async def create_dict_type(...):
    dict_type = await self.dict_type_crud.create(data)
    if self.redis:
        await self._refresh_cache_for_type(...)   # 刷新失败要重抛
    return dict_type

async def _refresh_cache_for_type(self, old, new, dict_type):
    if self.redis is None:
        return
    key = CacheService.sys_dict_cache_prefix + dict_type_dict_type
    await self.redis.delete(key)
    await self._save_type_to_cache(dict_type_dict_type, dict_type)
```

- 缓存 key 前缀在 `CacheService` 常量（如 `sys_dict_cache_prefix`）
- 批量更新：按 key 分组、每组只刷新一次（`old_key_by_id` / `new_key_by_id` 去重）
- 删除：收集 `deleted_keys`，循环外统一 `redis.delete(keys)`

## 依赖注入速查（app/api/v1/deps.py）

| 依赖 | 用途 |
| --- | --- |
| `AuthUser` | 已认证用户（Pydantic 模型：user_id / username / token / ...） |
| `AuthPermissionMixin` | 只做登录态校验，取 `auth` |
| `AuthPermission(["perm:..."])` | 校验具体权限标识 |
