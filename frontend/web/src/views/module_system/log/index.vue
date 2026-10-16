<!-- 日志管理：登录日志 + 操作日志 -->
<template>
  <div class="fa-full-height">
    <ElTabs v-model="activeTab" class="fa-tabs-fill">
      <ElTabPane v-if="checkPerm('module_system:log:query')" label="操作日志" name="operation">
        <FaSearchBar
          v-show="opShowSearchBar"
          ref="opSearchBarRef"
          v-model="opSearchForm"
          :items="opSearchItems"
          :rules="opSearchBarRules"
          :is-expand="false"
          :show-expand="true"
          :show-reset="true"
          :show-search="true"
          :disabled-search="false"
          :default-expanded="false"
          include-audit
          :audit-item-options="{ showCreatedBy: false, showUpdatedBy: false }"
          @search="handleOpSearch"
          @reset="onOpResetSearch"
        >
          <template #month>
            <ElSelect
              v-model="opMonth"
              :disabled="opLoading || opBatchDeleting || opDialogVisible.visible || opExportVisible"
              :clearable="false"
              style="width: 100%"
              @change="changeOpMonth"
            >
              <ElOption
                v-for="month in opMonths"
                :key="month"
                :value="month"
                :label="`${month.slice(0, 4)}-${month.slice(4)}`"
              />
            </ElSelect>
          </template>
        </FaSearchBar>

        <ElCard class="fa-table-card" :style="{ 'margin-top': opShowSearchBar ? '12px' : '0' }">
          <FaTableHeader
            v-model:columns="opColumnChecks"
            v-model:showSearchBar="opShowSearchBar"
            :loading="opLoading"
            @refresh="opRefreshData"
          >
            <template #left>
              <FaTableHeaderLeft
                :remove-ids="opSelectedIds"
                :perm-export="['module_system:log:export']"
                :perm-delete="['module_system:log:delete']"
                :delete-loading="opBatchDeleting"
                @export="openOpExport"
                @delete="handleOpBatchDelete"
              />
            </template>
          </FaTableHeader>

          <FaTable
            ref="opTableRef"
            :loading="opLoading"
            :data="opData"
            :columns="opColumns"
            :pagination="opPagination"
            @selection-change="onOpTableSelectionChange"
            @pagination:size-change="opHandleSizeChange"
            @pagination:current-change="opHandleCurrentChange"
          />
        </ElCard>

        <FaDialog
          v-model="opDialogVisible.visible"
          :title="opDialogVisible.title"
          width="960px"
          dialog-class="crud-embed-dialog"
          modal-class="crud-embed-dialog"
          form-mode="detail"
          @close="handleOpCloseDialog"
        >
          <FaDescriptions
            :column="8"
            :data="opFormData"
            :items="opDetailItems"
            label-width="200px"
            max-height="70vh"
          >
            <template #request_method="{ row }">
              <ElTag :type="getMethodType(row?.request_method as string)">{{
                row?.request_method
              }}</ElTag>
            </template>
            <template #response_code="{ row }">
              <ElTag :type="getStatusCodeType(row?.response_code as number)">{{
                row?.response_code
              }}</ElTag>
            </template>
            <template #request_payload="{ row }">
              <FaJsonPretty
                :value="(row as unknown as OperationLogTable)?.request_payload"
                height="80px"
              />
            </template>
            <template #response_json="{ row }">
              <FaJsonPretty
                :value="(row as unknown as OperationLogTable)?.response_json"
                height="140px"
              />
            </template>
          </FaDescriptions>
        </FaDialog>

        <FaExportDialog
          v-model="opExportVisible"
          :content-config="opExportContentConfig"
          :query-params="opExportQueryParams"
          :page-data="opData"
          :selection-data="opSelectedRows"
        />
      </ElTabPane>

      <ElTabPane v-if="checkPerm('module_system:login_log:query')" label="登录日志" name="login">
        <FaSearchBar
          v-show="loginShowSearchBar"
          ref="loginSearchBarRef"
          v-model="loginSearchForm"
          :items="loginSearchItems"
          :rules="loginSearchBarRules"
          :is-expand="false"
          :show-expand="true"
          :show-reset="true"
          :show-search="true"
          :disabled-search="false"
          :default-expanded="false"
          include-audit
          :audit-item-options="{ showCreatedBy: false, showUpdatedBy: false }"
          @search="handleLoginSearch"
          @reset="onLoginResetSearch"
        >
          <template #month>
            <ElSelect
              v-model="loginMonth"
              :disabled="loginLoading || loginBatchDeleting || loginDialogVisible.visible"
              :clearable="false"
              style="width: 100%"
              @change="changeLoginMonth"
            >
              <ElOption
                v-for="month in loginMonths"
                :key="month"
                :value="month"
                :label="`${month.slice(0, 4)}-${month.slice(4)}`"
              />
            </ElSelect>
          </template>
        </FaSearchBar>

        <ElCard class="fa-table-card" :style="{ 'margin-top': loginShowSearchBar ? '12px' : '0' }">
          <FaTableHeader
            v-model:columns="loginColumnChecks"
            v-model:showSearchBar="loginShowSearchBar"
            :loading="loginLoading"
            @refresh="loginRefreshData"
          >
            <template #left>
              <FaTableHeaderLeft
                :remove-ids="loginSelectedIds"
                :perm-delete="['module_system:login_log:delete']"
                :delete-loading="loginBatchDeleting"
                @delete="handleLoginBatchDelete"
              />
            </template>
          </FaTableHeader>

          <FaTable
            ref="loginTableRef"
            :loading="loginLoading"
            :data="loginData"
            :columns="loginColumns"
            :pagination="loginPagination"
            @selection-change="onLoginTableSelectionChange"
            @pagination:size-change="loginHandleSizeChange"
            @pagination:current-change="loginHandleCurrentChange"
          />
        </ElCard>

        <FaDialog
          v-model="loginDialogVisible.visible"
          :title="loginDialogVisible.title"
          width="640px"
          dialog-class="crud-embed-dialog"
          modal-class="crud-embed-dialog"
          form-mode="detail"
          @close="handleLoginCloseDialog"
        >
          <FaDescriptions
            :column="4"
            :data="loginFormData"
            :items="loginDetailItems"
            label-width="120px"
            max-height="70vh"
          >
            <template #status="{ row }">
              <ElTag :type="row?.status === 1 ? 'success' : 'danger'">{{
                row?.status === 1 ? "成功" : "失败"
              }}</ElTag>
            </template>
          </FaDescriptions>
        </FaDialog>
      </ElTabPane>
      <ElTabPane
        v-if="checkPerm('system:http_log:query')"
        :label="t('auditLog.httpTab')"
        name="http"
        lazy
      >
        <HttpLogPanel v-if="activeTab === 'http'" />
      </ElTabPane>
    </ElTabs>
  </div>
</template>

<script setup lang="ts">
import HttpLogPanel from "@/views/module_system/http_log/index.vue";
import { formatDateTime as formatLogTime, dateTimeFormValue } from "@/utils/dateTime";
import { checkPerm } from "@/utils/checkPerm";
import { useI18n } from "vue-i18n";
import { DictTypeEnum } from "@/constants/dict-types";
import { useDict } from "@/hooks/core/useDict";
const pageDict = useDict([DictTypeEnum.SYS_OPERATION_STATUS, DictTypeEnum.SYS_LOGIN_STATUS]);

import OperationLogAPI, {
  type OperationLogPageQuery,
  type OperationLogTable,
  type LoginLogTable,
  LoginLogAPI,
} from "@/api/module_system/log";
import {
  renderTableOperationCell,
  resolveStatusColumns,
  stripPaginationParams,
  cleanEmptyArrayParams,
  toCrudCols,
  type TableOperationAction,
  type StatusType,
} from "@utils";
import type { IObject } from "@/components/modal/types";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import type FaSearchBar from "@/components/forms/fa-search-bar/index.vue";
import FaStatusTag from "@/components/display/fa-status-tag/index.vue";
import FaCopyButton from "@/components/actions/fa-copy-button/index.vue";
import type { ColumnOption } from "@/types/component";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import FaDescriptions from "@/components/display/fa-descriptions/index.vue";

defineOptions({
  name: "Log",
  inheritAttrs: false,
});

const { t } = useI18n();
const currentMonth = () =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
  })
    .format(new Date())
    .replace(/[^0-9]/g, "");
const opMonth = ref(currentMonth());
const loginMonth = ref(currentMonth());
const opMonths = ref<string[]>([opMonth.value]);
const loginMonths = ref<string[]>([loginMonth.value]);

onMounted(async () => {
  const results = await Promise.allSettled([
    checkPerm("module_system:log:query") ? OperationLogAPI.months() : Promise.resolve(null),
    checkPerm("module_system:login_log:query") ? LoginLogAPI.months() : Promise.resolve(null),
  ]);
  if (results[0].status === "fulfilled")
    opMonths.value = [...new Set([currentMonth(), ...(results[0].value?.data.data ?? [])])]
      .sort()
      .reverse();
  if (results[1].status === "fulfilled")
    loginMonths.value = [...new Set([currentMonth(), ...(results[1].value?.data.data ?? [])])]
      .sort()
      .reverse();
});

const activeTab = ref<"operation" | "login" | "http">(
  checkPerm("module_system:log:query")
    ? "operation"
    : checkPerm("module_system:login_log:query")
      ? "login"
      : "http"
);

function handleIpSearch(ip: string) {
  if (opMonth.value !== loginMonth.value) {
    opMonth.value = loginMonth.value;
    void changeOpMonth();
  }
  activeTab.value = "operation";
  opSearchForm.value.request_ip = ip;
  opReplaceSearchParams(buildOpReplaceParams(opSearchForm.value));
  void opGetData();
}

// ==================== 操作日志 ====================

type OpSearchForm = {
  request_path?: string;
  request_ip?: string;
  created_time?: string[];
  updated_time?: string[];
};

const opSearchForm = ref<OpSearchForm>({
  request_path: undefined,
  request_ip: undefined,
  created_time: undefined,
  updated_time: undefined,
});
const opShowSearchBar = ref(true);
const opSearchBarRef = ref<InstanceType<typeof FaSearchBar> | null>(null);
const opSearchBarRules: Record<string, unknown> = {};

const opSearchItems = computed<SearchFormItem[]>(() => [
  {
    key: "month",
    label: t("auditLog.month"),
    type: "select",
    span: 6,
    props: { clearable: false },
  },
  {
    label: "请求路径",
    key: "request_path",
    type: "input",
    placeholder: "请输入请求路径",
    clearable: true,
    span: 6,
  },
  {
    label: "请求IP",
    key: "request_ip",
    type: "input",
    placeholder: "请输入请求IP",
    clearable: true,
    span: 6,
  },
]);

function buildOpReplaceParams(p: OpSearchForm): Record<string, unknown> {
  return {
    month: opMonth.value,
    order_by: JSON.stringify([{ created_time: "desc" }, { id: "desc" }]),
    request_path: p.request_path,
    request_ip: p.request_ip,
    created_time:
      Array.isArray(p.created_time) && p.created_time.length === 2
        ? p.created_time.map(dateTimeFormValue)
        : undefined,
    updated_time:
      Array.isArray(p.updated_time) && p.updated_time.length === 2
        ? p.updated_time.map(dateTimeFormValue)
        : undefined,
  };
}

const opTableRef = ref<{ elTableRef?: { clearSelection: () => void } } | null>(null);
const {
  selectedRows: opSelectedRows,
  selectedIds: opSelectedIds,
  batchDeleting: opBatchDeleting,
  onTableSelectionChange: onOpTableSelectionChange,
} = useTableSelection<OperationLogTable>();

const {
  columns: opColumns,
  columnChecks: opColumnChecks,
  data: opData,
  loading: opLoading,
  pagination: opPagination,
  searchParams: opSearchParams,
  getData: opGetData,
  replaceSearchParams: opReplaceSearchParams,
  handleSizeChange: opHandleSizeChange,
  handleCurrentChange: opHandleCurrentChange,
  refreshData: opRefreshData,
  refreshRemove: opRefreshRemove,
} = useTable({
  core: {
    apiFn: OperationLogAPI.list,
    immediate: checkPerm("module_system:log:query"),
    apiParams: {
      page_no: 1,
      page_size: 10,
      month: opMonth.value,
      order_by: JSON.stringify([{ created_time: "desc" }, { id: "desc" }]),
    },
    columnsFactory: (): ColumnOption<OperationLogTable>[] => [
      { type: "selection", width: 48, fixed: "left" },
      { type: "globalIndex", width: 56, label: "序号" },
      { prop: "request_path", label: "请求路径", minWidth: 200, showOverflowTooltip: true },
      {
        prop: "request_method",
        label: "请求方法",
        minWidth: 100,
        formatter: (row: OperationLogTable) =>
          h(FaStatusTag, {
            type: getMethodType(row.request_method),
            label: row.request_method ?? "",
          }),
      },
      {
        prop: "response_code",
        label: "状态码",
        minWidth: 100,
        formatter: (row: OperationLogTable) =>
          h(FaStatusTag, {
            type: getStatusCodeType(row.response_code),
            label: String(row.response_code ?? ""),
          }),
      },
      {
        prop: "request_ip",
        label: "请求IP",
        minWidth: 140,
        showOverflowTooltip: true,
        formatter: (row: OperationLogTable) => row.request_ip ?? "-",
      },
      { prop: "process_time", label: "处理时间", minWidth: 120 },
      { prop: "description", label: "描述", minWidth: 120, showOverflowTooltip: true },
      {
        prop: "created_time",
        formatter: (row) => formatLogTime(row.created_time),
        label: "创建时间",
        width: 168,
        sortable: true,
        showOverflowTooltip: true,
      },
      {
        prop: "operation",
        label: "操作",
        width: 160,
        fixed: "right",
        align: "center",
        formatter: (row: OperationLogTable) => formatOpActionCell(row),
      },
    ],
  },
});

const opCrudCols = toCrudCols(opColumns);

const opExportQueryParams = computed(() => {
  const sp = stripPaginationParams(opSearchParams as Record<string, unknown>);
  return cleanEmptyArrayParams({ ...sp }) as unknown as OperationLogPageQuery;
});

const opExportContentConfig = computed(() => ({
  permPrefix: "module_system:log",
  cols: opCrudCols.value,
  exportsBlobAction: async (params: IObject) => {
    const res = await OperationLogAPI.export(
      cleanEmptyArrayParams({
        ...(opExportQueryParams.value as unknown as Record<string, unknown>),
        ...params,
        month: opMonth.value,
      }) as OperationLogPageQuery
    );
    return res.data as Blob;
  },
}));

const opFormData = ref<OperationLogTable>({} as OperationLogTable);

const opDetailItems: import("@/components/display/fa-descriptions/index.vue").DescriptionsItem[] = [
  { label: "描述", prop: "description", span: 8 },
  { label: "请求路径", prop: "request_path" },
  { label: "请求方法", prop: "request_method", slot: "request_method" },
  { label: "响应状态码", prop: "response_code", slot: "response_code" },
  { label: "请求IP", prop: "request_ip" },
  { label: "处理时间", prop: "process_time" },
  { label: "请求参数", prop: "request_payload", slot: "request_payload", span: 8 },
  { label: "响应数据", prop: "response_json", slot: "response_json", span: 8 },
  { label: "创建时间", prop: "created_time" },
];

const { dialogVisible: opDialogVisible, closeDialog: opCloseDialog } = useCrudDialog();
const { exportVisible: opExportVisible, openExport: openOpExport } = useImportExport();

async function handleOpSearch(params: OpSearchForm) {
  await opSearchBarRef.value?.validate?.();
  opReplaceSearchParams(buildOpReplaceParams(params));
  await opGetData();
}

function onOpResetSearch() {
  opSearchForm.value = {
    request_path: undefined,
    request_ip: undefined,
    created_time: undefined,
    updated_time: undefined,
  };
  opReplaceSearchParams(buildOpReplaceParams(opSearchForm.value));
  void opGetData();
}

async function handleOpCloseDialog() {
  opCloseDialog();
  Object.assign(opFormData.value, {});
}

async function handleOpOpenDetail(id: string) {
  opDialogVisible.title = "操作日志详情";
  const response = await OperationLogAPI.detail(id, opMonth.value);
  Object.assign(opFormData.value, response.data.data ?? {});
  opFormData.value.created_time = formatLogTime(opFormData.value.created_time);
  opDialogVisible.visible = true;
}

async function deleteOpRow(id: string, name: string) {
  const month = opMonth.value;
  try {
    await confirmDelete(`确定删除「${name}」吗？`);
    await OperationLogAPI.delete([id], month);
    opTableRef.value?.elTableRef?.clearSelection();
    await opRefreshRemove();
  } catch {
    /* 用户取消 */
  }
}

function buildOpRowActions(row: OperationLogTable): TableOperationAction[] {
  const all: TableOperationAction[] = [
    {
      key: "detail",
      label: "详情",
      artType: "view",
      perm: "module_system:log:detail",
      run: () => {
        if (row.id != null) void handleOpOpenDetail(row.id);
      },
    },
    {
      key: "delete",
      label: "删除",
      artType: "delete",
      icon: "ri:delete-bin-4-line",
      perm: "module_system:log:delete",
      run: () => {
        if (row.id != null) deleteOpRow(row.id, row.description ?? String(row.id));
      },
    },
  ];
  return all;
}

function formatOpActionCell(row: OperationLogTable) {
  return renderTableOperationCell(buildOpRowActions(row), {
    wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 log-table-actions",
  });
}

async function handleOpBatchDelete() {
  const month = opMonth.value;
  const ids = opSelectedIds.value;
  if (ids.length === 0) return;
  try {
    await confirmBatchDelete(
      ids.length,
      opSelectedRows.value.map((r) => String(r.description ?? r.id))
    );
    opBatchDeleting.value = true;
    await OperationLogAPI.delete(ids, month);
    opTableRef.value?.elTableRef?.clearSelection();
    await opRefreshRemove();
  } catch {
    /* 用户取消 */
  } finally {
    opBatchDeleting.value = false;
  }
}

// ==================== 登录日志 ====================

type LoginSearchForm = {
  username?: string;
  status?: number;
  created_time?: string[];
  updated_time?: string[];
};

const loginSearchForm = ref<LoginSearchForm>({
  username: undefined,
  status: undefined,
  created_time: undefined,
  updated_time: undefined,
});
const loginShowSearchBar = ref(true);
const loginSearchBarRef = ref<InstanceType<typeof FaSearchBar> | null>(null);
const loginSearchBarRules: Record<string, unknown> = {};

const LOGIN_STATUS_OPTIONS = pageDict.options(DictTypeEnum.SYS_LOGIN_STATUS, "number");

const loginSearchItems = computed<SearchFormItem[]>(() => [
  {
    key: "month",
    label: t("auditLog.month"),
    type: "select",
    span: 6,
    props: { clearable: false },
  },
  {
    label: "用户名",
    key: "username",
    type: "input",
    placeholder: "请输入用户名",
    clearable: true,
    span: 6,
  },
  {
    label: "登录状态",
    key: "status",
    type: "select",
    props: { placeholder: "请选择状态", options: LOGIN_STATUS_OPTIONS, clearable: true },
    span: 6,
  },
  {
    label: "登录时间",
    key: "created_time",
    type: "datetimerange",
    span: 6,
    props: {
      type: "datetimerange",
      rangeSeparator: "至",
      startPlaceholder: "开始日期",
      endPlaceholder: "结束日期",
      format: "YYYY-MM-DD HH:mm:ss",
      valueFormat: "YYYY-MM-DD HH:mm:ss",
      style: { width: "100%" },
    },
  },
]);

function buildLoginReplaceParams(p: LoginSearchForm): Record<string, unknown> {
  return {
    month: loginMonth.value,
    order_by: JSON.stringify([{ created_time: "desc" }, { id: "desc" }]),
    username: p.username || undefined,
    status:
      p.status !== undefined && p.status !== null && p.status !== ("" as unknown as number)
        ? Number(p.status)
        : undefined,
    created_time:
      Array.isArray(p.created_time) && p.created_time.length === 2
        ? p.created_time.map(dateTimeFormValue)
        : undefined,
    updated_time:
      Array.isArray(p.updated_time) && p.updated_time.length === 2
        ? p.updated_time.map(dateTimeFormValue)
        : undefined,
  };
}

const loginTableRef = ref<{ elTableRef?: { clearSelection: () => void } } | null>(null);
const {
  selectedIds: loginSelectedIds,
  batchDeleting: loginBatchDeleting,
  onTableSelectionChange: onLoginTableSelectionChange,
} = useTableSelection<LoginLogTable>();

const {
  columns: loginColumns,
  columnChecks: loginColumnChecks,
  data: loginData,
  loading: loginLoading,
  pagination: loginPagination,
  getData: loginGetData,
  replaceSearchParams: loginReplaceSearchParams,
  handleSizeChange: loginHandleSizeChange,
  handleCurrentChange: loginHandleCurrentChange,
  refreshData: loginRefreshData,
  refreshRemove: loginRefreshRemove,
} = useTable({
  core: {
    apiFn: LoginLogAPI.list,
    immediate: checkPerm("module_system:login_log:query"),
    apiParams: {
      page_no: 1,
      page_size: 10,
      month: loginMonth.value,
      order_by: JSON.stringify([{ created_time: "desc" }, { id: "desc" }]),
    },
    columnsFactory: resolveStatusColumns<LoginLogTable>(() => [
      { type: "selection", width: 48, fixed: "left" },
      { type: "globalIndex", width: 56, label: "序号" },
      {
        prop: "status",
        label: "登录状态",
        width: 88,
        status: pageDict.tagMap(DictTypeEnum.SYS_OPERATION_STATUS),
      },
      { prop: "username", label: "用户名", minWidth: 120, showOverflowTooltip: true },
      {
        prop: "login_ip",
        label: "登录IP",
        minWidth: 190,
        formatter: (row: LoginLogTable) =>
          row.login_ip
            ? h("span", { class: "inline-flex items-center gap-0.5 whitespace-nowrap" }, [
                h(
                  "span",
                  {
                    class: "ip-link-cell",
                    title: "点击搜索该IP",
                    onClick: () => handleIpSearch(row.login_ip!),
                  },
                  [row.login_ip ?? ""]
                ),
                h(FaCopyButton, { text: row.login_ip, style: { marginLeft: "2px" } }),
              ])
            : "-",
      },
      { prop: "login_location", label: "登录地点", minWidth: 160, showOverflowTooltip: true },
      { prop: "request_os", label: "操作系统", minWidth: 120 },
      { prop: "request_browser", label: "浏览器", minWidth: 180, showOverflowTooltip: true },
      { prop: "msg", label: "提示消息", minWidth: 200, showOverflowTooltip: true },
      {
        prop: "created_time",
        formatter: (row) => formatLogTime(row.created_time),
        label: "登录时间",
        width: 168,
        sortable: true,
        showOverflowTooltip: true,
      },
      {
        prop: "operation",
        label: "操作",
        width: 120,
        fixed: "right",
        align: "center",
        formatter: (row: LoginLogTable) => formatLoginActionCell(row),
      },
    ]),
  },
});

const loginFormData = ref<LoginLogTable>({} as LoginLogTable);

const loginDetailItems = [
  { label: "登录状态", prop: "status", slot: "status" },
  { label: "用户名", prop: "username" },
  { label: "登录IP", prop: "login_ip" },
  { label: "登录地点", prop: "login_location" },
  { label: "操作系统", prop: "request_os" },
  { label: "浏览器", prop: "request_browser" },
  { label: "提示消息", prop: "msg", span: 2 },
  { label: "登录时间", prop: "created_time" },
];

const { dialogVisible: loginDialogVisible, closeDialog: loginCloseDialog } = useCrudDialog();

async function handleLoginSearch(params: LoginSearchForm) {
  await loginSearchBarRef.value?.validate?.();
  loginReplaceSearchParams(buildLoginReplaceParams(params));
  await loginGetData();
}

function onLoginResetSearch() {
  loginSearchForm.value = {
    username: undefined,
    status: undefined,
    created_time: undefined,
    updated_time: undefined,
  };
  loginReplaceSearchParams(buildLoginReplaceParams(loginSearchForm.value));
  void loginGetData();
}

async function handleLoginOpenDetail(id: string) {
  loginDialogVisible.title = "登录日志详情";
  const response = await LoginLogAPI.detail(id, loginMonth.value);
  Object.assign(loginFormData.value, response.data.data ?? {});
  loginFormData.value.created_time = formatLogTime(loginFormData.value.created_time);
  loginDialogVisible.visible = true;
}

function handleLoginCloseDialog() {
  loginCloseDialog();
}

async function deleteLoginRow(id: string, name: string) {
  const month = loginMonth.value;
  try {
    await confirmDelete(`确定删除「${name}」吗？`);
    await LoginLogAPI.delete([id], month);
    loginTableRef.value?.elTableRef?.clearSelection();
    await loginRefreshRemove();
  } catch {
    /* 用户取消 */
  }
}

function buildLoginRowActions(row: LoginLogTable): TableOperationAction[] {
  const all: TableOperationAction[] = [
    {
      key: "detail",
      label: "详情",
      artType: "view",
      perm: "module_system:login_log:query",
      run: () => {
        if (row.id != null) void handleLoginOpenDetail(row.id);
      },
    },
    {
      key: "delete",
      label: "删除",
      artType: "delete",
      icon: "ri:delete-bin-4-line",
      perm: "module_system:login_log:delete",
      run: () => {
        if (row.id != null) deleteLoginRow(row.id, row.username ?? String(row.id));
      },
    },
  ];
  return all;
}

function formatLoginActionCell(row: LoginLogTable) {
  return renderTableOperationCell(buildLoginRowActions(row), {
    wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 loginlog-table-actions",
  });
}

async function handleLoginBatchDelete() {
  const month = loginMonth.value;
  const ids = loginSelectedIds.value;
  if (ids.length === 0) return;
  try {
    await confirmBatchDelete(
      ids.length,
      (loginData.value as LoginLogTable[])
        .filter((r) => ids.includes(r.id!))
        .map((r) => String(r.username ?? r.id))
    );
    loginBatchDeleting.value = true;
    await LoginLogAPI.delete(ids, month);
    loginTableRef.value?.elTableRef?.clearSelection();
    await loginRefreshRemove();
  } catch {
    /* 用户取消 */
  } finally {
    loginBatchDeleting.value = false;
  }
}

// 修复：登录日志 tab 在组件挂载时数据已请求但 DOM 未就绪，首次切换到时重新请求
const loginTabLoaded = ref(false);
watch(activeTab, (tab) => {
  if (tab === "login" && !loginTabLoaded.value) {
    loginTabLoaded.value = true;
    nextTick(() => {
      void loginGetData();
    });
  }
});

async function changeOpMonth() {
  opTableRef.value?.elTableRef?.clearSelection();
  onOpTableSelectionChange([]);
  opData.value = [];
  opSearchForm.value.created_time = undefined;
  opSearchForm.value.updated_time = undefined;
  opReplaceSearchParams(buildOpReplaceParams(opSearchForm.value));
  await opGetData();
}

async function changeLoginMonth() {
  loginTableRef.value?.elTableRef?.clearSelection();
  onLoginTableSelectionChange([]);
  loginData.value = [];
  loginSearchForm.value.created_time = undefined;
  loginSearchForm.value.updated_time = undefined;
  loginReplaceSearchParams(buildLoginReplaceParams(loginSearchForm.value));
  await loginGetData();
}

// ==================== 通用 ====================

function getStatusCodeType(code?: number): StatusType {
  if (code === undefined) return "info";
  if (code >= 200 && code < 300) return "success";
  if (code >= 300 && code < 400) return "warning";
  return "danger";
}

function getMethodType(method?: string): StatusType {
  if (method === undefined) return "info";
  if (method === "GET") return "info";
  if (method === "POST") return "success";
  if (method === "PUT" || method === "PATCH") return "warning";
  if (method === "DELETE") return "danger";
  return "info";
}
</script>
