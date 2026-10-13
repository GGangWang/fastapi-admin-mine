# 字典管理与枚举字典

字典管理采用 `sys_dict_info` 单表。根节点为类型，`parent_id` 为空、`dict_level=0`，且 `dict_type=dict_code`。后代保留相同 `dict_type`，不存 `root_id`。层级与类型由后端维护，调用方不能提交或覆盖。

同级编码唯一，同级最多一个默认项；不同分支允许同值。根节点编码为小写字母开头的字母、数字、下划线。父节点停用后业务查询隐藏整条分支，不覆盖后代的自身状态。有未删除子节点时不能删除；不允许跨类型移动、根节点转子项或循环引用。

## 枚举注册

在 `backend/app/modules/system/dict/registry.py` 显式注册。`DictItem` 声明值、标签、排序、状态、默认项、样式、备注；`children` 声明直接子项，或通过 `children_enum` 指定成员值为 `DictItem` 的 Python Enum，两者互斥。

```python
from enum import Enum
from app.modules.system.dict.registry import DictItem, EnumDictionary, REGISTRY

class ResourceState(Enum):
    ONLINE = DictItem("online", "在线", sort=1, list_class="success")
    OFFLINE = DictItem("offline", "离线", sort=2, list_class="info")

REGISTRY.register(EnumDictionary("resource_state", "资源状态", enum=ResourceState))
```

枚举无需入库。默认注册 `sys_business_status`、`sys_true_false`、`sys_business_type`。原有性别、通知类型继续由数据库维护。内部枚举不会自动暴露。枚举类型编码保留，数据库与枚举同码时启动失败；枚举定义重复、同级值重复、默认项冲突或引用循环时注册失败。

统一响应提供 `source` 和 `readonly`。数据库节点 ID 为整数；枚举 ID 为字符串，根据类型及完整编码路径稳定生成，不可作为数据库主键写入。业务值按字符串返回，前导零保留，布尔值为 `true` / `false`。

## API

以下路径相对 `/api/v1/system/dict`：

| 方法与路径 | 行为 |
| --- | --- |
| `GET /nodes` | 当前父节点下分页；不传 parent_id 返回类型目录，支持名称、编码、来源、状态筛选 |
| `GET /nodes/{key}` | 节点详情 |
| `GET /nodes/{key}/ancestors` | 根到当前节点的路径 |
| `POST /nodes`、`PUT /nodes/{key}` | 创建或完整更新数据库节点；parent_id 决定归属 |
| `DELETE /nodes` | 请求体为 ID 数组；整体校验后软删除 |
| `GET /children/{key}` | 当前可用直接子项，祖先停用时返回空数组，适用于懒加载级联 |
| `GET /tree/{dict_type}` | 可用业务树，不包含类型根节点；迭代编码以支持深层树 |
| `POST /types` | `{"dict_types": [...]}`，批量返回各类型的一级选项 |
| `POST /cache/refresh` | 刷新全部字典缓存代次 |
| `POST /export?tree=true` | 导出筛选类型的整树；省略 tree 导出当前层级 |
| `GET /type/list`、`GET /type/optionselect` | 保留类型目录查询，供代码生成器使用 |
| `GET /data/info/{dict_type}` | 保留一级选项格式 `dict_label / dict_value / dict_type_id` |

写入 DTO：`parent_id`、`dict_name`、`dict_code`、`dict_sort`、`status`、`is_default`、`css_class`、`list_class`、`description`。父节点 ID 只能是数据库整数。枚举不支持新增、修改、删除、排序或停用。

权限继续使用 `module_system:dict_type:*` 和 `module_system:dict_data:*`；根与子项分别校验，枚举写入由后端再次拒绝。刷新缓存使用类型更新权限。管理页面由 `parent` 路由查询参数保存位置；来源统一展示，枚举只读。树预览和级联选择按当前父节点懒加载。

## 迁移与部署

迁移版本 `20261013_dict_tree` 将旧类型映射为根、旧数据映射为一级子项。旧表保持原样；`legacy_type_id`、`legacy_data_id` 保存新旧映射。迁移前校验重复编码、默认项及类型关联，失败时禁止覆盖。审计时间、UUID、状态、样式和软删除记录保留。新库直接使用 `backend/sql/sys_dict_info.json` 初始化。

部署前备份数据库，在后端目录执行 `uv run main.py upgrade --env=dev`（生产改为 prod），然后重启后端。也可由正常启动流程自动应用已提交迁移。不能继续运行旧版本后端写入旧字典表。回退应恢复切换前数据库备份和旧版本代码，迁移 downgrade 明确拒绝有损压回两表。

数据库修改在事务提交成功后更新缓存代次；失败回滚不发布新代次。读取缓存时带代次，旧快照不会回填新代次。枚举缓存带定义签名；前端持久化字典 Store 升级为 V2，并在更新操作后清空，本地缓存最多保留 30 秒。

操作日志也在请求事务成功提交后使用独立会话写入，避免响应后台任务在请求连接释放前争用连接池或 SQLite 写锁。

验证包括 75 级树读写与移动、1500 级树编码、循环拦截、同级编码和默认项约束、迁移幂等、来源合并分页、枚举只读、跨类型权限、HTTP 写入后缓存可见性及迁移一致性检查。MySQL/PostgreSQL 的实际迁移仍需在目标环境进行演练。

## 本次验证记录（2026-10-13）

- 字典与迁移相关 12 项检查通过；后端完整测试 107 项通过，3 项失败来自原有演示模块异常处理及域名默认值断言。
- 新字典模块 Ruff 检查通过；前端类型检查只剩原有演示页面的 3 处转换错误。
- 前端生产构建通过，已同步 `backend/dist` 和 `docker/nginx/web/dist`。
- 后续数据库恢复后已验证开发 MySQL：迁移版本为 `20261013_dict_tree`，新表 7 条记录，旧类型表 2 条、旧数据表 5 条均保留。真实数据库的增改、重命名传播、停用分支及删除保护验证通过，临时验证数据已回滚。

## ResNexus 名称升级

产品显示名称、CLI、日志、包名、默认数据库/容器配置及部署文档统一使用 ResNexus（工程标识使用小写 `resnexus`）。开发库中的上游默认品牌参数已更新，Redis 参数及字典缓存已刷新；运行中后端的 OpenAPI 标题、健康检查、数据库字典和枚举字典 HTTP 查询验证通过。

原始 LICENSE 声明保留。`app/common/legacy_identifiers.py` 中仅保留历史 KDF 上下文和调度锁标识，用于解密存量密文及避免混合版本重复调度；升级 SQL 的旧值匹配条件也必须保留。既有本地环境文件的数据库连接名和凭据不改动，新安装的默认数据库名为 `resnexus`。工作区目录和 Git 历史未重命名。

新写入密文采用 ResNexus KDF 标识，仍支持原 KDF 密文及旧主密钥轮换；升级时应整体重启后端，避免旧节点读取新版本密文或使用不同 SSE 通道。名称升级相关的加密兼容、字典、迁移和安全默认值共 53 项专项测试通过，ResNexus 前端生产构建通过并同步部署产物；前端类型检查仍有原有演示页面的 3 处转换错误。
