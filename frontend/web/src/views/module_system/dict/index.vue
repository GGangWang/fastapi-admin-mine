<template>
  <div class="fa-full-height flex flex-col gap-3">
    <ElBreadcrumb separator="/" class="px-2 py-2">
      <ElBreadcrumbItem v-for="node in breadcrumb" :key="node.id" @click="navigate(node.id)">
        <a>{{ node.dict_name }}</a>
      </ElBreadcrumbItem>
    </ElBreadcrumb>
    <FaSearchBar
      v-model="search"
      :items="searchItems"
      :is-expand="false"
      @search="searchRows"
      @reset="resetSearch"
    />
    <ElCard class="fa-table-card flex-1 min-h-0">
      <FaTableHeader :loading="loading" layout="refresh" @refresh="loadRows">
        <template #left>
          <FaTableHeaderLeft>
            <ElButton
              v-if="!parent?.readonly"
              v-hasPerm="
                parent ? 'module_system:dict_data:create' : 'module_system:dict_type:create'
              "
              type="primary"
              :icon="Plus"
              plain
              @click="openForm()"
              >{{ t("dictionary.add") }}</ElButton
            >
            <ElButton
              v-if="parent"
              :icon="Back"
              plain
              @click="navigate(parent.parent_id ?? undefined)"
            >
              {{ t("dictionary.back") }}
            </ElButton>
            <ElButton
              v-hasPerm="
                parent ? 'module_system:dict_data:export' : 'module_system:dict_type:export'
              "
              type="warning"
              :icon="Download"
              plain
              @click="exportFile(false)"
              >{{ t("dictionary.export") }}</ElButton
            >
            <ElButton
              v-if="!parent"
              v-hasPerm="'module_system:dict_type:export'"
              type="warning"
              :icon="Share"
              plain
              @click="exportFile(true)"
              >{{ t("dictionary.exportTree") }}</ElButton
            >
            <ElButton
              v-hasPerm="'module_system:dict_type:update'"
              type="danger"
              :icon="Refresh"
              plain
              @click="refreshCache"
              >{{ t("dictionary.refreshCache") }}</ElButton
            >
            <ElTag v-if="parent?.readonly" type="info">{{ t("dictionary.enumReadonly") }}</ElTag>
          </FaTableHeaderLeft>
        </template>
      </FaTableHeader>
      <FaTable
        :data="rows"
        :columns="columns"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        disable-row-drag
        @pagination:current-change="changePage"
        @pagination:size-change="changeSize"
      >
        <template #name="{ row }">
          <ElTag v-if="row.list_class" :type="tagType(row.list_class)">{{ row.dict_name }}</ElTag>
          <span v-else>{{ row.dict_name }}</span>
        </template>
        <template #source="{ row }"
          ><ElTag :type="row.readonly ? 'info' : 'primary'">{{
            pageDict.label(DictTypeEnum.SYS_DICT_SOURCE, row.source)
          }}</ElTag></template
        >
        <template #status="{ row }"
          ><ElTag :type="row.status === EnableStatusValue.ENABLED ? 'success' : 'danger'">{{
            pageDict.label(DictTypeEnum.SYS_ENABLE_STATUS, row.status)
          }}</ElTag></template
        >
        <template #isDefault="{ row }">{{
          pageDict.label(DictTypeEnum.SYS_TRUE_FALSE, row.is_default)
        }}</template>
        <template #actions="{ row }">
          <ElTooltip :content="t('dictionary.children')" placement="top">
            <FaButtonTable
              type="add"
              icon="ri:node-tree"
              role="button"
              :aria-label="t('dictionary.children')"
              @click="navigate(row.id)"
            />
          </ElTooltip>
          <ElTooltip :content="t('dictionary.detail')" placement="top">
            <FaButtonTable
              type="view"
              role="button"
              :aria-label="t('dictionary.detail')"
              @click="openForm(row, true)"
            />
          </ElTooltip>
          <ElTooltip v-if="!row.readonly" :content="t('dictionary.edit')" placement="top">
            <FaButtonTable
              v-hasPerm="
                row.dict_level === 0
                  ? 'module_system:dict_type:update'
                  : 'module_system:dict_data:update'
              "
              type="edit"
              role="button"
              :aria-label="t('dictionary.edit')"
              @click="openForm(row)"
            />
          </ElTooltip>
          <ElTooltip v-if="!row.readonly" :content="t('dictionary.delete')" placement="top">
            <FaButtonTable
              v-hasPerm="
                row.dict_level === 0
                  ? 'module_system:dict_type:delete'
                  : 'module_system:dict_data:delete'
              "
              type="delete"
              role="button"
              :aria-label="t('dictionary.delete')"
              @click="remove(row)"
            />
          </ElTooltip>
          <ElTooltip v-if="row.dict_level === 0" :content="t('dictionary.preview')" placement="top">
            <FaButtonTable
              type="more"
              icon="ri:organization-chart"
              role="button"
              :aria-label="t('dictionary.preview')"
              @click="preview(row)"
            />
          </ElTooltip>
        </template>
      </FaTable>
    </ElCard>
    <FaDialog
      v-model="dialog"
      :title="dialogTitle"
      width="680px"
      :form-mode="readOnly ? 'detail' : editing ? 'update' : 'create'"
      :confirm-loading="saving"
      @confirm="save"
      @cancel="dialog = false"
    >
      <ElAlert
        v-if="readOnly"
        :title="editing?.readonly ? t('dictionary.enumReadonly') : t('dictionary.detail')"
        type="info"
        :closable="false"
        class="mb-3"
      />
      <FaForm
        ref="formRef"
        v-model="form"
        :items="formItems"
        :rules="rules"
        :disabled="readOnly"
        :show-reset="false"
        :show-submit="false"
        :span="24"
        :label-width="110"
      />
    </FaDialog>
    <FaDialog
      v-model="treeDialog"
      :title="t('dictionary.preview')"
      width="720px"
      form-mode="detail"
      @cancel="treeDialog = false"
    >
      <ElTree
        v-if="previewRoot"
        :key="previewRoot.id"
        :data="[previewRoot]"
        node-key="id"
        lazy
        :load="loadTree"
        :props="{ label: 'dict_name', isLeaf: 'leaf' }"
      />
      <div class="mt-4">{{ t("dictionary.choosePath") }}</div>
      <ElCascader
        v-if="previewRoot"
        :key="`select:${previewRoot.id}`"
        v-model="selectedPath"
        class="w-full mt-2"
        :options="[asOption(previewRoot)]"
        :props="cascaderProps"
        clearable
      />
      <div class="mt-2 text-sm">{{ selectedPath.join(" / ") }}</div>
    </FaDialog>
  </div>
</template>

<script setup lang="ts">
import { EnableStatusValue } from "@/enums/status.enum";

import { Back, Download, Plus, Refresh, Share } from "@element-plus/icons-vue";

import { DictTypeEnum } from "@/constants/dict-types";
import { useDict } from "@/hooks/core/useDict";
const pageDict = useDict([
  DictTypeEnum.SYS_DICT_SOURCE,
  DictTypeEnum.SYS_ENABLE_STATUS,
  DictTypeEnum.SYS_TRUE_FALSE,
]);

import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { ElMessage, ElMessageBox } from "element-plus";
import type { CascaderProps } from "element-plus";
import type { LoadFunction } from "element-plus/es/components/tree/src/tree.type";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import DictAPI, {
  type DictNode,
  type DictNodeId,
  type DictNodeQuery,
  type DictNodeWrite,
} from "@/api/module_system/dict";
import { useDictStore } from "@stores";

defineOptions({ name: "Dict" });
const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const dictStore = useDictStore();
const rows = ref<DictNode[]>([]);
const breadcrumb = ref<DictNode[]>([]);
const parent = computed(() => breadcrumb.value.at(-1));
const search = ref<Record<string, any>>({});
const pagination = ref({ current: 1, size: 10, total: 0 });
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const readOnly = ref(false);
const editing = ref<DictNode>();
const formRef = ref<{ validate: () => Promise<boolean> }>();
const form = ref<Record<string, any>>({});
let requestVersion = 0;
const columns = computed(() => [
  {
    prop: "dict_name",
    label: t("dictionary.name"),
    useSlot: true,
    slotName: "name",
    minWidth: 160,
    align: "center",
  },
  {
    prop: "dict_code",
    label: t("dictionary.code"),
    minWidth: 150,
    formatter: (row: DictNode) => row.dict_code,
    align: "center",
  },
  {
    prop: "dict_level",
    label: t("dictionary.level"),
    width: 70,
    formatter: (row: DictNode) => row.dict_level,
    align: "center",
  },
  {
    prop: "dict_sort",
    label: t("dictionary.sort"),
    width: 70,
    formatter: (row: DictNode) => row.dict_sort,
    align: "center",
  },
  {
    prop: "source",
    label: t("dictionary.source"),
    useSlot: true,
    slotName: "source",
    width: 100,
    align: "center",
  },
  {
    prop: "status",
    label: t("dictionary.status"),
    useSlot: true,
    slotName: "status",
    width: 85,
    align: "center",
  },
  {
    prop: "is_default",
    label: t("dictionary.default"),
    useSlot: true,
    slotName: "isDefault",
    width: 85,
  },
  {
    prop: "description",
    label: t("dictionary.description"),
    minWidth: 130,
    formatter: (row: DictNode) => row.description ?? "",
  },
  {
    prop: "actions",
    label: t("dictionary.actions"),
    useSlot: true,
    slotName: "actions",
    width: 300,
    fixed: "right" as const,
  },
]);
const statusOptions = computed(() => pageDict.options(DictTypeEnum.SYS_ENABLE_STATUS, "number"));
const searchItems = computed<SearchFormItem[]>(() => [
  { key: "dict_name", label: t("dictionary.name"), type: "input", span: 6 },
  { key: "dict_code", label: t("dictionary.code"), type: "input", span: 6 },
  {
    key: "source",
    label: t("dictionary.source"),
    type: "select",
    props: {
      clearable: true,
      options: pageDict.options(DictTypeEnum.SYS_DICT_SOURCE),
    },
    span: 6,
  },
  {
    key: "status",
    label: t("dictionary.status"),
    type: "select",
    props: { clearable: true, options: statusOptions.value },
    span: 6,
  },
]);
const formItems = computed<FormItem[]>(() => [
  { key: "dict_name", label: t("dictionary.name"), type: "input", props: { maxlength: 255 } },
  { key: "dict_code", label: t("dictionary.code"), type: "input", props: { maxlength: 255 } },
  {
    key: "parent_path",
    label: t("dictionary.parent"),
    type: "cascader",
    hidden: !form.value.parent_id || readOnly.value,
    props: {
      options: breadcrumb.value[0] ? [asOption(breadcrumb.value[0])] : [],
      props: parentCascaderProps,
      clearable: false,
    },
  },
  {
    key: "dict_sort",
    label: t("dictionary.sort"),
    type: "number",
    props: { min: 0, precision: 0 },
  },
  {
    key: "status",
    label: t("dictionary.status"),
    type: "radiogroup",
    props: { options: statusOptions.value },
  },
  {
    key: "is_default",
    label: t("dictionary.default"),
    type: "switch",
    hidden: !form.value.parent_id,
  },
  { key: "css_class", label: t("dictionary.cssClass"), type: "input" },
  {
    key: "list_class",
    label: t("dictionary.listClass"),
    type: "select",
    props: {
      clearable: true,
      options: ["primary", "success", "info", "warning", "danger"].map((value) => ({
        value,
        label: value,
      })),
    },
  },
  {
    key: "description",
    label: t("dictionary.description"),
    type: "input",
    props: { type: "textarea", rows: 3, maxlength: 2000 },
  },
]);
const rules = computed(() => ({
  dict_name: [{ required: true, message: t("dictionary.required"), trigger: "blur" }],
  dict_code: [{ required: true, message: t("dictionary.required"), trigger: "blur" }],
}));
const dialogTitle = computed(() =>
  t(readOnly.value ? "dictionary.detail" : editing.value ? "dictionary.edit" : "dictionary.add")
);

function currentQuery(): DictNodeQuery {
  return {
    ...search.value,
    parent_id: route.query.parent ? String(route.query.parent) : undefined,
    page_no: pagination.value.current,
    page_size: pagination.value.size,
  };
}
async function loadRows() {
  const version = ++requestVersion;
  loading.value = true;
  try {
    const query = currentQuery();
    const [listResponse, pathResponse] = await Promise.all([
      DictAPI.listNodes(query),
      query.parent_id ? DictAPI.ancestors(query.parent_id) : Promise.resolve(undefined),
    ]);
    if (version !== requestVersion) return;
    rows.value = listResponse.data.data.items;
    pagination.value.total = listResponse.data.data.total;
    breadcrumb.value = pathResponse?.data.data ?? [];
  } finally {
    if (version === requestVersion) loading.value = false;
  }
}
function navigate(key?: DictNodeId) {
  router.push({ path: route.path, query: key === undefined ? {} : { parent: String(key) } });
}
function searchRows() {
  pagination.value.current = 1;
  void loadRows();
}
function resetSearch() {
  search.value = {};
  searchRows();
}
function changePage(page: number) {
  pagination.value.current = page;
  void loadRows();
}
function changeSize(size: number) {
  pagination.value.size = size;
  searchRows();
}
function openForm(row?: DictNode, detail = false) {
  editing.value = row;
  readOnly.value = detail || !!row?.readonly;
  form.value = {
    parent_id: row ? row.parent_id : (parent.value?.id ?? null),
    parent_path: breadcrumb.value.map((node) => node.id),
    dict_name: row?.dict_name ?? "",
    dict_code: row?.dict_code ?? "",
    dict_sort: row?.dict_sort ?? 0,
    status: row?.status ?? EnableStatusValue.ENABLED,
    is_default: row?.is_default ?? false,
    css_class: row?.css_class ?? "",
    list_class: row?.list_class ?? "",
    description: row?.description ?? "",
  };
  dialog.value = true;
}
async function save() {
  if (readOnly.value || saving.value || !(await formRef.value?.validate())) return;
  saving.value = true;
  try {
    const { parent_path, ...values } = form.value;
    if (values.parent_id !== null && Array.isArray(parent_path) && parent_path.length) {
      values.parent_id = Number(parent_path.at(-1));
    }
    await DictAPI.saveNode(values as DictNodeWrite, editing.value?.id);
    dictStore.clearDictData();
    dialog.value = false;
    ElMessage.success(t("dictionary.saved"));
    await loadRows();
  } finally {
    saving.value = false;
  }
}
async function remove(row: DictNode) {
  await ElMessageBox.confirm(
    t("dictionary.confirmDelete", { name: row.dict_name }),
    t("dictionary.delete"),
    { type: "warning" }
  );
  await DictAPI.deleteNodes([row.id]);
  dictStore.clearDictData();
  await loadRows();
}
async function refreshCache() {
  await DictAPI.refreshCache();
  dictStore.clearDictData();
  ElMessage.success(t("dictionary.saved"));
}
async function exportFile(tree: boolean) {
  const response = await DictAPI.exportNodes(currentQuery(), tree);
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = tree ? "dictionary-tree.xlsx" : "dictionary.xlsx";
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function tagType(value: string) {
  return ["primary", "success", "info", "warning", "danger"].includes(value)
    ? (value as "primary" | "success" | "info" | "warning" | "danger")
    : "info";
}
const treeDialog = ref(false);
const previewRoot = ref<DictNode>();
const selectedPath = ref<DictNodeId[]>([]);
function preview(row: DictNode) {
  previewRoot.value = row;
  selectedPath.value = [];
  treeDialog.value = true;
}
const loadTree: LoadFunction = async (node, resolve) => {
  if (node.level === 0) {
    resolve(previewRoot.value ? [previewRoot.value] : []);
    return;
  }
  try {
    resolve(
      (await DictAPI.children(node.data.id)).data.data.map((row) => ({
        ...row,
        leaf: !row.has_children,
      }))
    );
  } catch {
    resolve([]);
  }
};
function asOption(row: DictNode) {
  return { value: row.id, label: row.dict_name, leaf: !row.has_children };
}
const cascaderProps: CascaderProps = {
  lazy: true,
  checkStrictly: true,
  async lazyLoad(node, resolve) {
    if (node.level === 0) {
      resolve(previewRoot.value ? [asOption(previewRoot.value)] : []);
      return;
    }
    try {
      resolve((await DictAPI.children(node.value as DictNodeId)).data.data.map(asOption));
    } catch {
      resolve([]);
    }
  },
};
const parentCascaderProps: CascaderProps = {
  lazy: true,
  checkStrictly: true,
  async lazyLoad(node, resolve) {
    if (node.level === 0) {
      resolve(breadcrumb.value[0] ? [asOption(breadcrumb.value[0])] : []);
      return;
    }
    try {
      resolve(
        (await DictAPI.children(node.value as DictNodeId)).data.data
          .filter((row) => row.source === "database")
          .map((row) => ({
            value: row.id,
            label: row.dict_name,
            disabled: row.id === editing.value?.id,
            leaf: !row.has_children,
          }))
      );
    } catch {
      resolve([]);
    }
  },
};
watch(
  () => route.query.parent,
  () => {
    pagination.value.current = 1;
    search.value = {};
    void loadRows();
  },
  { immediate: true }
);
</script>
