<template>
  <div class="fa-full-height">
    <FaSearchBar
      v-show="showSearchBar"
      ref="searchBarRef"
      v-model="searchForm"
      :items="businessSearchItems"
      :rules="searchBarRules"
      :is-expand="false"
      :show-expand="true"
      :show-reset="true"
      :show-search="true"
      :disabled-search="false"
      :default-expanded="false"
      include-audit
      @search="handleSearch"
      @reset="onResetSearch"
    />

    <ElCard class="fa-table-card" :style="{ 'margin-top': showSearchBar ? '12px' : '0' }">
      <FaTableHeader
        v-model:columns="columnChecks"
        v-model:showSearchBar="showSearchBar"
        :loading="loading"
        @refresh="refreshData"
      >
        <template #left>
          <FaTableHeaderLeft
            :remove-ids="selectedIds"
            :perm-create="['module_demo:test_demo_base:create']"
            :perm-import="['module_demo:test_demo_base:import']"
            :perm-export="['module_demo:test_demo_base:export']"
            :perm-delete="['module_demo:test_demo_base:delete']"
            :perm-patch="['module_demo:test_demo_base:patch']"
            :delete-loading="batchDeleting"
            :create-loading="createLoading"
            :more-loading="moreLoading"
            @add="handleAdd"
            @import="openImport"
            @export="openExport"
            @delete="handleBatchDelete"
            @more="handleMoreClick"
          />
        </template>
      </FaTableHeader>

      <FaTable
        ref="faTableRef"
        :loading="loading"
        :data="data"
        :columns="columns"
        :pagination="pagination"
        @selection-change="onTableSelectionChange"
        @pagination:size-change="handleSizeChange"
        @pagination:current-change="handleCurrentChange"
      />
    </ElCard>

    <FaDialog
      v-model="dialogVisible.visible"
      :title="dialogVisible.title"
      width="920px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      :form-mode="dialogVisible.type"
      :confirm-loading="submitLoading"
      @cancel="handleCloseDialog"
      @close="handleCloseDialog"
      @confirm="handleSubmit()"
    >
      <template v-if="dialogVisible.type === 'detail'">
        <FaDescriptions :column="4" :data="detailFormData" :items="detailItems" max-height="70vh">
          <template #user_sex="{ value }">
            {{ sexLabel(value as number) }}
          </template>
        </FaDescriptions>
      </template>
      <template v-else>
        <FaForm
          :key="formRenderKey"
          scrollbar
          max-height="70vh"
          ref="dataFormRef"
          v-model="formData"
          :items="dialogFormItems"
          :rules="rules"
          label-suffix=":"
          :label-width="100"
          label-position="right"
          :span="12"
          :gutter="16"
          :show-reset="false"
          :show-submit="false"
          class="crud-dialog-art-form"
        />
      </template>
    </FaDialog>

    <FaImportDialog
      v-model="importVisible"
      :content-config="importContentConfig"
      default-template-file-name="test_demo_base_import_template.xlsx"
      @upload="handleCrudImportUpload"
    />

    <FaExportDialog
      v-model="exportVisible"
      :content-config="exportContentConfig"
      :query-params="exportQueryParams"
      :page-data="data"
      :selection-data="selectedRows"
    />
  </div>
</template>

<script setup lang="ts">
import { EnableStatusValue } from "@/enums/status.enum";

import { DictTypeEnum } from "@/constants/dict-types";
import { useDict } from "@/hooks/core/useDict";
const pageDict = useDict([DictTypeEnum.SYS_USER_SEX, DictTypeEnum.SYS_ENABLE_STATUS]);

import {
  renderTableOperationCell,
  resolveStatusColumns,
  stripPaginationParams,
  toCrudCols,
  type TableOperationAction,
} from "@utils";
import { useCrudForm } from "@/hooks/core/useCrudForm";
import { ResultEnum } from "@/enums/api/result.enum";
import type { IContentConfig, IObject } from "@/components/modal/types";
import type { AuditSearchFormParams } from "@/components/forms/fa-search-bar/auditSearchFormItems";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import FaDescriptions from "@/components/display/fa-descriptions/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import TestDemoBaseAPI, {
  type TestDemoBaseForm,
  type TestDemoBasePageQuery,
  type TestDemoBaseTable,
} from "@/api/module_demo/test_demo_base";

defineOptions({
  name: "TestDemoBase",
  inheritAttrs: false,
});

// 常量定义
const STATUS_OPTIONS = pageDict.options(DictTypeEnum.SYS_ENABLE_STATUS, "number");

const createInitialFormData = (): TestDemoBaseForm => ({
  user_name: undefined,
  user_sex: undefined,
});

type TestDemoBaseSearchFormParams = {
  user_name?: string;
  user_sex?: string;
} & AuditSearchFormParams;

const searchForm = ref<TestDemoBaseSearchFormParams>({
  user_name: undefined,
  user_sex: undefined,
  created_id: undefined,
  updated_id: undefined,
  created_time: undefined,
  updated_time: undefined,
});

/** 搜索区域默认展开展示 */
const showSearchBar = ref(true);

const searchBarRef = ref<{ validate: () => Promise<boolean> } | null>(null);
const searchBarRules: Record<string, unknown> = {};

/** 业务搜索项（审计四字段由 FaSearchBar 的 includeAudit 属性追加） */
const businessSearchItemsRaw = computed<SearchFormItem[]>(() => [
  {
    label: "用户名",
    key: "user_name",
    type: "input",
    placeholder: "请输入用户名",
    clearable: true,
    span: 6,
  },
  {
    label: "性别",
    key: "user_sex",
    type: "select",
    props: {
      placeholder: "请选择性别",
      options: [],
      clearable: true,
    },
    span: 6,
  },
]);

const businessSearchItems = computed(() => {
  const items = businessSearchItemsRaw.value.map((item) => ({ ...item }));
  const item_user_sex = items.find((i: any) => i.key === "user_sex");
  if (item_user_sex && item_user_sex.props) {
    item_user_sex.props.options = pageDict.options(DictTypeEnum.SYS_USER_SEX);
  }
  return items;
});

const faTableRef = ref<{ elTableRef?: { clearSelection: () => void } } | null>(null);
const { selectedRows, selectedIds, batchDeleting, onTableSelectionChange } =
  useTableSelection<TestDemoBaseTable>();

const createLoading = ref(false);
const moreLoading = ref(false);

const PK = "id" as const;

const {
  columns,
  columnChecks,
  data,
  loading,
  pagination,
  searchParams,
  getData,
  replaceSearchParams,
  resetSearchParams,
  handleSizeChange,
  handleCurrentChange,
  refreshData,
  refreshCreate,
  refreshUpdate,
  refreshRemove,
} = useTable({
  core: {
    apiFn: TestDemoBaseAPI.listTestDemoBase,
    apiParams: {
      page_no: 1,
      page_size: 10,
    },
    columnsFactory: resolveStatusColumns<TestDemoBaseTable>(() => [
      { type: "selection", width: 48, fixed: "left" },
      { type: "globalIndex", width: 56, label: "序号" },
      {
        prop: "created_time",
        label: "创建时间",
        width: 168,
        sortable: true,
        showOverflowTooltip: true,
      },
      {
        prop: "updated_time",
        label: "更新时间",
        width: 168,
        sortable: true,
        showOverflowTooltip: true,
      },
      {
        prop: "created_by",
        label: "创建人",
        minWidth: 100,
        formatter: (row: TestDemoBaseTable) => row.created_by?.name ?? "—",
      },
      {
        prop: "updated_by",
        label: "更新人",
        minWidth: 100,
        formatter: (row: TestDemoBaseTable) => row.updated_by?.name ?? "—",
      },
      { prop: "user_name", label: "用户名", minWidth: 120, showOverflowTooltip: true },
      {
        prop: "user_sex",
        label: "性别",
        minWidth: 120,
        showOverflowTooltip: true,
        formatter: (row: TestDemoBaseTable) => sexLabel(row.user_sex),
      },
      {
        prop: "operation",
        label: "操作",
        width: 180,
        fixed: "right",
        align: "center",
        formatter: (row: TestDemoBaseTable) => formatOperationCell(row),
      },
    ]),
  },
});

const crudCols = toCrudCols(columns);

const exportQueryParams = computed(() => {
  return stripPaginationParams(searchParams as Record<string, unknown>);
});

const importContentConfig = computed<IContentConfig>(() => ({
  permPrefix: "module_demo:test_demo_base",
  cols: crudCols.value,
  indexAction: async () => ({}),
  importTemplate: () => TestDemoBaseAPI.downloadTemplateTestDemoBase(),
}));

const exportContentConfig = computed(() => ({
  permPrefix: "module_demo:test_demo_base",
  cols: crudCols.value,
  exportsBlobAction: async (params: IObject) => {
    const merged = {
      ...(exportQueryParams.value as unknown as Record<string, unknown>),
      ...params,
    } as unknown as TestDemoBasePageQuery;
    const res = await TestDemoBaseAPI.exportTestDemoBase(merged);
    return res.data as Blob;
  },
}));

const { dialogVisible } = useCrudDialog();

const detailFormData = ref<TestDemoBaseTable>({});

const detailItems: import("@/components/display/fa-descriptions/index.vue").DescriptionsItem[] = [
  { label: "创建时间", prop: "created_time" },
  { label: "更新时间", prop: "updated_time" },
  { label: "创建人", prop: "created_by.name" },
  { label: "更新人", prop: "updated_by.name" },
  { label: "用户名", prop: "user_name" },
  { label: "性别", prop: "user_sex", slot: "user_sex" },
];

const formData = ref<TestDemoBaseForm>(createInitialFormData());

const rules = reactive({
  user_name: [{ required: false, message: "请填写用户名", trigger: "blur" }],
  user_sex: [{ required: false, message: "请填写性别", trigger: "blur" }],
});

const dialogFormItems = computed<FormItem[]>(() => [
  { key: "user_name", label: "用户名", type: "input", props: { placeholder: "请输入用户名" } },
  {
    key: "user_sex",
    label: "性别",
    type: "select",
    placeholder: "请选择性别",
    options: pageDict.options(DictTypeEnum.SYS_USER_SEX),
  },
]);

/** 性别字典标签（渲染时读取，字典异步加载后自动更新） */
function sexLabel(val?: string | number) {
  return pageDict.label(DictTypeEnum.SYS_USER_SEX, val);
}

const dataFormRef = ref<InstanceType<typeof FaForm> | null>(null);
const formRenderKey = ref(0);

const crud = useCrudForm<TestDemoBaseForm>({
  formData,
  initialFormData: createInitialFormData(),
  dialogVisible,
  dataFormRef,
  formRenderKey,
  detailApi: (id: number) => TestDemoBaseAPI.detailTestDemoBase(id),
  createApi: (data: TestDemoBaseForm) => TestDemoBaseAPI.createTestDemoBase(data),
  updateApi: (id: number, data: TestDemoBaseForm) => TestDemoBaseAPI.updateTestDemoBase(id, data),
  titles: { create: "新增", update: "修改", detail: "详情" },
  detailFormData,
  onCreateSuccess: async () => {
    await refreshCreate();
  },
  onUpdateSuccess: async () => {
    await refreshUpdate();
  },
});

const { submitLoading } = crud;

const { importVisible, exportVisible, openImport, openExport } = useImportExport();

const handleSearch = async (params: TestDemoBaseSearchFormParams) => {
  await searchBarRef.value?.validate();
  replaceSearchParams({
    user_name: params.user_name,
    user_sex: params.user_sex,
    created_id: params.created_id ?? undefined,
    updated_id: params.updated_id ?? undefined,
    created_time:
      Array.isArray(params.created_time) && params.created_time.length === 2
        ? params.created_time
        : undefined,
    updated_time:
      Array.isArray(params.updated_time) && params.updated_time.length === 2
        ? params.updated_time
        : undefined,
  } as Record<string, unknown>);
  await getData();
};

const onResetSearch = async () => {
  searchForm.value = {
    user_name: undefined,
    user_sex: undefined,
    created_id: undefined,
    updated_id: undefined,
    created_time: undefined,
    updated_time: undefined,
  };
  await resetSearchParams();
};

function buildRowActions(row: TestDemoBaseTable): TableOperationAction[] {
  const all: TableOperationAction[] = [
    {
      key: "detail",
      label: "详情",
      artType: "view",
      perm: "module_demo:test_demo_base:detail",
      run: () => void crud.handleOpenDialog("detail", row[PK] as number),
    },
    {
      key: "edit",
      label: "编辑",
      artType: "edit",
      icon: "ri:edit-2-line",
      perm: "module_demo:test_demo_base:update",
      run: () => void crud.handleOpenDialog("update", row[PK] as number),
    },
    {
      key: "delete",
      label: "删除",
      artType: "delete",
      icon: "ri:delete-bin-4-line",
      perm: "module_demo:test_demo_base:delete",
      run: () => deleteRow(row),
    },
  ];
  return all;
}

function formatOperationCell(row: TestDemoBaseTable) {
  return renderTableOperationCell(buildRowActions(row), {
    wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1",
  });
}

async function handleAdd() {
  createLoading.value = true;
  try {
    await crud.handleOpenDialog("create");
  } finally {
    createLoading.value = false;
  }
}

async function handleCloseDialog() {
  await crud.handleCloseDialog();
}

async function handleSubmit() {
  await crud.handleSubmit();
}

const deleteRow = async (row: TestDemoBaseTable) => {
  if (!row[PK]) return;
  try {
    await confirmDelete(`确定删除该基础测试管理吗？此操作不可恢复！`);
    await TestDemoBaseAPI.deleteTestDemoBase([row[PK] as number]);
    faTableRef.value?.elTableRef?.clearSelection();
    await refreshRemove();
  } catch {
    // 用户取消
  }
};

async function handleBatchDelete() {
  const ids = selectedIds.value;
  if (ids.length === 0) return;
  try {
    await confirmBatchDelete(
      ids.length,
      selectedRows.value.map((row) => String(row["uuid"] ?? ""))
    );
    batchDeleting.value = true;
    await TestDemoBaseAPI.deleteTestDemoBase(ids);
    faTableRef.value?.elTableRef?.clearSelection();
    await refreshRemove();
  } catch {
    // 用户取消
  } finally {
    batchDeleting.value = false;
  }
}

async function handleMoreClick(value: "enable" | "disable") {
  const ids = selectedIds.value;
  if (ids.length === 0) {
    ElMessage.warning("请先在列表中勾选数据");
    return;
  }
  try {
    await confirmToggleStatus(value);
    moreLoading.value = true;
    const status = value === "enable" ? EnableStatusValue.ENABLED : EnableStatusValue.DISABLED;
    await TestDemoBaseAPI.batchTestDemoBase({ ids, status });
    // 成功 / 失败提示由 axios 拦截器统一处理
    faTableRef.value?.elTableRef?.clearSelection();
    await refreshData();
  } catch {
    // 用户取消或操作失败
  } finally {
    moreLoading.value = false;
  }
}

async function handleCrudImportUpload(formData: FormData) {
  try {
    const res = await TestDemoBaseAPI.importTestDemoBase(formData);
    if (res.data.code === ResultEnum.SUCCESS) {
      ElMessage.success(res.data.msg || "导入成功");
      importVisible.value = false;
      await refreshData();
    }
    // 非 SUCCESS 分支提示由 axios 拦截器统一处理
  } catch (error: unknown) {
    if (import.meta.env.DEV) console.error("[Import]", error);
    /* 接口错误已由拦截器提示 */
  }
}

// 页面挂载时加载一次性别字典（搜索/弹窗/列表/详情复用同一份缓存）
onMounted(async () => {
  await pageDict.ready;
});
</script>

<style lang="scss" scoped></style>
