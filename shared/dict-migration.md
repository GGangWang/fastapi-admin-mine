# 统一字典接入与迁移清单

维护入口：`shared/dict-types.json`。执行 `python scripts/generate_dict_types.py` 生成两端常量；`--check` 校验一致性。新增固定程序字典还需在后端显式注册，数据库字典仍由管理页维护。

页面用法：
```ts
const pageDict = useDict([DictTypeEnum.SYS_USER_SEX, DictTypeEnum.SYS_ENABLE_STATUS]);
const options = pageDict.options(DictTypeEnum.SYS_ENABLE_STATUS, "number");
// 页面声明一次，表单、搜索及表格共享数据；布尔字段显式使用 "boolean"。
```
```vue
<FaDictTag :type="DictTypeEnum.SYS_USER_SEX" :value="row.gender" />
```

已迁移：字典、用户、菜单、角色/权限抽屉、部门、岗位、公告、日志、版本、工单、代码生成、个人中心、示例、定时任务/节点、存储节点/浏览/传输/工作流，以及公共用户选择器。字段编码保持原值；性别和公告类型继续使用现有数据库来源，其余新增固定程序选项为只读枚举。不新增数据库字典，因此无需表结构或数据迁移；不覆盖用户维护的数据。

后端批量接口：`POST /system/dict/types`，`{dict_types: [...], mode: "flat" | "tree"}`。省略 mode 保持原来的一级选项响应。树形响应仍省略类型根节点。未知类型返回空数组，前端正常缓存；网络失败不伪造选项。

缓存：30 秒有效，flat/tree 隔离；持久化 key 升为 V4。退出登录、字典修改及刷新清理缓存。活跃页面刷新，缓存页激活时检查有效期。进行中的旧请求在清理后不能写回。

保留例外：
- 字典页 `list_class` 选项是 Element Plus 视觉样式，与主题、布局和编辑器配置同属前端视觉配置。
- 用户、部门、角色、资源、存储节点等实体列表由专用 API 提供；存储协议 API 提供当前后端支持能力，标签由字典转换。
- 文件大小单位、Cron 表达式格式化、业务操作按钮文案和流程图配色属于格式化/界面行为，不作为业务字典。
- 生成器的用户配置 dict_type 为运行期元数据，通过 resolveDictType 解析，支持框架发布后新增的自定义数据库字典。

部署：先更新并重启后端以注册枚举，再更新前端。运行前后端测试、`pnpm ts:check`、`pnpm build:prod`；镜像同步 backend/dist 和 docker/nginx/web/dist。既有基础演示页的三处字符串到数字断言错误单独记录。

验证记录：前端字典及真实 FaTable 交互测试 9 项通过；后端字典测试 13 项、模板测试 29 项通过；生产构建通过。类型检查仅保留基础演示页三处既有 TS2352。实际后端已验证 flat/tree 批量响应、枚举顺序和样式；浏览器登录后回归受滑块验证阻挡，未绕过。

## 后端业务值枚举

业务值集中定义在 `backend/app/common/dict_values.py`，与类型编码 `DictType` 分离。字典注册通过 `DictItem(TicketStatus.PENDING.value, "待处理", ...)` 引用；标签、排序、样式仍配置在注册文件。整数使用 IntEnum，字符串使用 StrEnum，布尔使用 BooleanValue 的 `.value`，保留原始存储类型。

```python
from app.common.dict_values import TicketStatus, TransferStatus, StorageProtocol

if ticket.status == TicketStatus.PENDING:
    ticket.status = TicketStatus.PROCESSING.value

if task.status == TransferStatus.SUCCESS:
    ...
```

已有 TicketTypeEnum 继续复用；StorageProtocol 的旧导入路径 `app.modules.task.storage.core.base` 保留为兼容导出，引用的是同一个枚举类。不同业务的登录结果与操作结果、任务取消 `cancelled` 与传输取消 `canceled` 保持独立编码。

启停状态自2026-10-14起统一为1启用/正常、0停用/禁用；公告使用独立发布状态字典。迁移及回退说明见 [status-encoding-migration.md](./status-encoding-migration.md)。
