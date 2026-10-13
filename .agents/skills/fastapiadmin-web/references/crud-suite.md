# CRUD 套件拆解（dict 为样例）

参考页面：`views/module_system/dict/index.vue` + `api/module_system/dict.ts`。

## 1. API 层模板

```ts
// api/module_system/dict.ts（节选）
import { request } from "@utils";

const API_PATH = "/system/dict";

const DictAPI = {
  listDictType(query: DictPageQuery) {
    return request<ApiResponse<PageResult<DictTable>>>({
      url: `${API_PATH}/type/list`,
      method: "get",
      params: query,
    });
  },
  detailDictType(query: number) {
    return request<ApiResponse<DictTable>>({ url: `${API_PATH}/type/detail/${query}`, method: "get" });
  },
  createDictType(body: DictForm) {
    return request<ApiResponse>({ url: `${API_PATH}/type/create`, method: "post", data: body });
  },
  updateDictType(id: number, body: DictForm) {
    return request<ApiResponse>({ url: `${API_PATH}/type/update/${id}`, method: "put", data: body });
  },
  deleteDictType(body: number[]) {
    return request<ApiResponse>({ url: `${API_PATH}/type/delete`, method: "delete", data: body });
  },
  batchDictType(body: BatchType) {
    return request<ApiResponse>({ url: `${API_PATH}/type/status/batch`, method: "patch", data: body });
  },
  exportDictType(body: DictPageQuery) {
    return request<Blob>({ url: `${API_PATH}/type/export`, method: "post", data: body, responseType: "blob" });
  },
};

export default DictAPI;
// 类型定义同文件：query 继承 PageQuery，行继承 BaseType，表单继承 BaseFormType
```

约定：
- 方法命名 `listX / optionSelectX / detailX / createX / updateX / deleteX / batchX / exportX`
- URL 与后端 controller 路径一一对齐
- 导出走 `Blob` + `responseType: "blob"`，下载用 `useImportExport`
- 泛型全局可用（`ApiResponse<T>`、`PageResult<T>`、`PageQuery`、`BaseType`、`BaseFormType`、`BatchType`），不必本地声明

## 2. 页面骨架（index.vue）

```
<div class="fa-full-height">
  FaSearchBar        <!-- searchForm + items + rules；@search / @reset -->
  ElCard.fa-table-card
    FaTableHeader    <!-- v-model:columns（列显隐）/ v-model:showSearchBar；#left → FaTableHeaderLeft :perm-create -->
    FaTable          <!-- :loading :data :columns :pagination；@pagination:size-change / current-change -->
  FaDialog           <!-- 详情 → FaDescriptions；新增/编辑 → FaForm -->
</div>
```

要点：
- `FaTableHeaderLeft :perm-create="['module_system:dict_type:create']"`——新增按钮由权限驱动
- 行操作用 `buildXxxRowActions(row): TableOperationAction[]` 定义、`renderTableOperationCell` 渲染；每个 action 带 `perm`（如 `module_system:dict_type:update`），无权限不显示
- 分页：FaTable 分页事件 → useTable 的 `handleSizeChange` / `handleCurrentChange`
- 搜索：`FaSearchBar @search` → 校验后 `replaceSearchParams` 合并 → `getData()`；reset 走 `resetSearchParams`
- 页面私有子组件放 `views/.../components/`（如字典右侧面板 `DictDataPanel`；父级用 `:key` 在切换字典时强制重建）

## 3. Hook 职责表

| Hook | 职责 |
| --- | --- |
| `useTable` | data / loading / pagination / `getData` / `refreshData` / `refreshRemove` |
| `useCrudDialog` + `useCrudForm` | 弹窗状态、formData、rules、`handleSubmit`（详情/创建/更新） |
| `useTableColumns` | 列显隐 `columnChecks`（配合 FaTableHeader） |
| `useAuth` | 代码内 `hasAuth(...)` 权限判断 |
| `useImportExport` | 导入 / 导出（导出走 Blob 下载） |
| `useConfirm` | `confirmDelete(...)` 等确认弹窗 |

## 4. 权限两段式

- 页面按钮：`v-hasPerm` / `:perm-create` / 行 action `perm`
- 代码内：`const { hasAuth } = useAuth()`
- 标识格式 `module_x:resource:operation`（dict_type / dict_data / query / detail / create / update / delete / patch），必须与后端 `AuthPermission([...])` 及 sys_menu 按钮权限一致

## 5. 有状态页面

- `defineOptions({ name: "..." })` = 菜单 route_name（KeepAlive 按组件名匹配）
- 连接/定时器类页面实现 `onActivated` / `onDeactivated`（坑见 SKILL.md）
- 字典类缓存：写操作后 `dictStore.clearDictData()` + `getDict(...)` 刷新前端字典缓存
