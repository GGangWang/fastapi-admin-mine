<template>
  <div class="fa-full-height flex flex-col gap-3">
    <FaSearchBar
      v-model="search"
      :items="searchItems"
      :is-expand="false"
      :show-expand="true"
      :show-reset="true"
      :show-search="true"
      :default-expanded="false"
      @search="searchRows"
      @reset="resetSearch"
    >
      <template #month>
        <ElSelect
          v-model="month"
          :clearable="false"
          style="width: 100%"
          :placeholder="t('httpLog.month')"
          @change="changeMonth"
        >
          <ElOption
            v-for="item in months"
            :key="item"
            :label="`${item.slice(0, 4)}-${item.slice(4)}`"
            :value="item"
          />
        </ElSelect>
      </template>
    </FaSearchBar>
    <ElCard class="fa-table-card flex-1 min-h-0">
      <FaTableHeader :loading="loading" layout="refresh" @refresh="loadRows" />
      <FaTable
        :loading="loading"
        :data="rows"
        :columns="columns"
        :pagination="pagination"
        @pagination:current-change="changePage"
        @pagination:size-change="changeSize"
      >
        <template #method="{ row }"
          ><FaDictTag :type="DictTypeEnum.SYS_HTTP_METHOD" :value="row.method"
        /></template>
        <template #result="{ row }"
          ><FaDictTag :type="DictTypeEnum.SYS_HTTP_RESULT" :value="row.result"
        /></template>
        <template #actions="{ row }">
          <ElTooltip :content="t('httpLog.detail')"
            ><FaButtonTable
              v-hasPerm="'system:http_log:detail'"
              type="view"
              role="button"
              :aria-label="t('httpLog.detail')"
              tabindex="0"
              @keydown.enter="openDetail(row)"
              @click="openDetail(row)"
          /></ElTooltip>
        </template>
      </FaTable>
    </ElCard>
    <ElDrawer v-model="drawer" :title="t('httpLog.detail')" size="min(960px, 95vw)">
      <template v-if="detail">
        <ElDescriptions :column="2" border>
          <ElDescriptionsItem v-for="key in detailKeys" :key="key" :label="fieldLabel(key)">
            <FaDictTag
              v-if="key === 'result'"
              :type="DictTypeEnum.SYS_HTTP_RESULT"
              :value="detail[key]"
            />
            <FaDictTag
              v-else-if="key === 'method'"
              :type="DictTypeEnum.SYS_HTTP_METHOD"
              :value="detail[key]"
            />
            <span v-else class="break-all whitespace-pre-wrap">{{
              key === "started_at" ? formatLogTime(detail.started_at) : (detail[key] ?? "—")
            }}</span>
          </ElDescriptionsItem>
        </ElDescriptions>
        <ElTabs v-model="side" @tab-change="resetBody">
          <ElTabPane :label="t('httpLog.request')" name="request" />
          <ElTabPane :label="t('httpLog.response')" name="response" />
        </ElTabs>
        <pre class="http-log-text">{{ headerText }}</pre>
        <div class="flex flex-wrap gap-2 my-3 items-center">
          <ElTag>{{ bodyState }}</ElTag>
          <ElButton
            v-hasPerm="'system:http_log:body'"
            :loading="bodyLoading"
            :disabled="!recorded"
            @click="loadBody(0)"
            >{{ t("httpLog.loadBody") }}</ElButton
          >
          <ElButton
            v-hasPerm="'system:http_log:download'"
            :disabled="!recorded"
            @click="downloadBody"
            >{{ t("httpLog.download") }}</ElButton
          >
          <template v-if="bodyPage">
            <ElButton :disabled="offsets.length < 2 || bodyLoading" @click="previousBody">{{
              t("httpLog.previous")
            }}</ElButton>
            <ElButton :disabled="!bodyPage.has_next || bodyLoading" @click="nextBody">{{
              t("httpLog.next")
            }}</ElButton>
            <span
              >{{ bodyPage.offset }}–{{ bodyPage.next_offset }} / {{ bodyPage.total_bytes }} B</span
            >
            <ElButton v-if="bodyPage.total_bytes <= 65536" @click="formatBody">{{
              t("httpLog.format")
            }}</ElButton>
            <ElButton @click="copyBody">{{ t("httpLog.copy") }}</ElButton>
          </template>
        </div>
        <pre v-if="bodyPage" v-loading="bodyLoading" class="http-log-text">{{ bodyText }}</pre>
      </template>
    </ElDrawer>
  </div>
</template>
<script setup lang="ts">
import { formatDateTime as formatLogTime, dateTimeFormValue, beijingTime } from "@/utils/dateTime";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { ElMessage } from "element-plus";
import HttpLogAPI, { type HttpLog, type HttpBodyPage } from "@/api/module_system/http-log";
import { DictTypeEnum } from "@/constants/dict-types";
import { useDict } from "@/hooks/core/useDict";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
defineOptions({ name: "HttpLog" });
const { t } = useI18n();
const dict = useDict([DictTypeEnum.SYS_HTTP_METHOD, DictTypeEnum.SYS_HTTP_RESULT]);
const month = ref(beijingTime().format("YYYYMM"));
const months = ref<string[]>([]);
const search = ref<Record<string, any>>({});
const rows = ref<HttpLog[]>([]);
const loading = ref(false);
const pagination = ref({ current: 1, size: 20, total: 0 });
let listVersion = 0;
const fieldLabel = (key: string) => t(`httpLog.fields.${key}`);
const columns = computed(() => [
  ...[
    "started_at",
    "service",
    "business",
    "method",
    "url",
    "status_code",
    "result",
    "duration_ms",
    "request_bytes",
    "response_bytes",
    "operator",
  ].map((prop) => ({
    prop,
    label: fieldLabel(prop),
    minWidth: prop === "url" ? 260 : 120,
    showOverflowTooltip: true,
    ...(["method", "result"].includes(prop)
      ? { useSlot: true, slotName: prop }
      : {
          formatter: (row: HttpLog) =>
            prop === "started_at"
              ? formatLogTime(row.started_at)
              : (row[prop as keyof HttpLog] ?? "—"),
        }),
  })),
  {
    prop: "actions",
    label: t("httpLog.actions"),
    width: 80,
    fixed: "right" as const,
    useSlot: true,
    slotName: "actions",
  },
]);
const searchItems = computed<SearchFormItem[]>(() => [
  {
    key: "month",
    label: t("auditLog.month"),
    type: "select",
    span: 6,
    props: { clearable: false },
  },
  ...["service", "business", "url", "operator", "id", "correlation_id"].map((key) => ({
    key,
    label: fieldLabel(key),
    type: "input" as const,
    span: 6,
  })),
  {
    key: "method",
    label: fieldLabel("method"),
    type: "select",
    span: 6,
    props: { clearable: true, options: dict.options(DictTypeEnum.SYS_HTTP_METHOD) },
  },
  {
    key: "result",
    label: fieldLabel("result"),
    type: "select",
    span: 6,
    props: { clearable: true, options: dict.options(DictTypeEnum.SYS_HTTP_RESULT) },
  },
  { key: "status_code", label: fieldLabel("status_code"), type: "number", span: 6 },
  {
    key: "start_time",
    label: t("httpLog.start"),
    type: "datetime",
    span: 6,
    props: { valueFormat: "YYYY-MM-DD HH:mm:ss", disabledDate },
  },
  {
    key: "end_time",
    label: t("httpLog.end"),
    type: "datetime",
    span: 6,
    props: { valueFormat: "YYYY-MM-DD HH:mm:ss", disabledDate },
  },
]);
function disabledDate(value: Date) {
  return `${value.getFullYear()}${String(value.getMonth() + 1).padStart(2, "0")}` !== month.value;
}
async function loadRows() {
  const version = ++listVersion;
  if (!months.value.includes(month.value)) {
    rows.value = [];
    pagination.value.total = 0;
    return;
  }
  loading.value = true;
  try {
    const result = await HttpLogAPI.list({
      ...search.value,
      start_time: search.value.start_time ? dateTimeFormValue(search.value.start_time) : undefined,
      end_time: search.value.end_time ? dateTimeFormValue(search.value.end_time) : undefined,
      month: month.value,
      page_no: pagination.value.current,
      page_size: pagination.value.size,
    });
    if (version === listVersion) {
      rows.value = result.data.data.items;
      pagination.value.total = result.data.data.total;
    }
  } finally {
    if (version === listVersion) loading.value = false;
  }
}
function searchRows() {
  pagination.value.current = 1;
  void loadRows();
}
function resetSearch() {
  search.value = {};
  searchRows();
}
function changeMonth() {
  drawer.value = false;
  search.value.start_time = undefined;
  search.value.end_time = undefined;
  searchRows();
}
function changePage(value: number) {
  pagination.value.current = value;
  void loadRows();
}
function changeSize(value: number) {
  pagination.value.size = value;
  searchRows();
}
const drawer = ref(false);
const detail = ref<HttpLog>();
const detailMonth = ref("");
const side = ref("request");
const detailKeys: (keyof HttpLog)[] = [
  "id",
  "correlation_id",
  "started_at",
  "service",
  "business",
  "operator",
  "method",
  "url",
  "status_code",
  "result",
  "duration_ms",
  "request_bytes",
  "response_bytes",
  "error",
];
const bodyPage = ref<HttpBodyPage>();
const bodyText = ref("");
const bodyLoading = ref(false);
const offsets = ref<number[]>([]);
let bodyVersion = 0;
let detailVersion = 0;
const recorded = computed(
  () => detail.value?.[`${side.value}_body_state` as keyof HttpLog] === "recorded"
);
const bodyState = computed(() =>
  t(
    `httpLog.states.${detail.value?.[`${side.value}_body_state` as keyof HttpLog] || "not_recorded"}`
  )
);
const headerText = computed(() => {
  const text = detail.value?.[`${side.value}_headers` as keyof HttpLog];
  try {
    return JSON.stringify(JSON.parse(String(text || "[]")), null, 2);
  } catch {
    return String(text || "");
  }
});
function resetBody() {
  ++bodyVersion;
  bodyLoading.value = false;
  bodyPage.value = undefined;
  bodyText.value = "";
  offsets.value = [];
}
async function openDetail(row: HttpLog) {
  const version = ++detailVersion;
  detailMonth.value = month.value;
  const result = await HttpLogAPI.detail(detailMonth.value, row.id);
  if (version !== detailVersion) return;
  detail.value = result.data.data;
  side.value = "request";
  resetBody();
  drawer.value = true;
}
async function loadBody(offset: number, remember = true) {
  if (!detail.value) return;
  const version = ++bodyVersion;
  bodyLoading.value = true;
  try {
    const response = await HttpLogAPI.body(detailMonth.value, detail.value.id, side.value, offset);
    if (version !== bodyVersion) return;
    bodyPage.value = response.data.data;
    bodyText.value = bodyPage.value.text;
    if (offset === 0) offsets.value = [0];
    else if (remember) offsets.value.push(offset);
  } finally {
    if (version === bodyVersion) bodyLoading.value = false;
  }
}
function nextBody() {
  if (bodyPage.value) void loadBody(bodyPage.value.next_offset);
}
function previousBody() {
  offsets.value.pop();
  void loadBody(offsets.value.at(-1) || 0, false);
}
function formatBody() {
  try {
    bodyText.value = JSON.stringify(JSON.parse(bodyPage.value?.text || ""), null, 2);
  } catch {
    ElMessage.info(t("httpLog.notJson"));
  }
}
async function copyBody() {
  await navigator.clipboard.writeText(bodyText.value);
  ElMessage.success(t("httpLog.copied"));
}
async function downloadBody() {
  if (!detail.value) return;
  const response = await HttpLogAPI.ticket(detailMonth.value, detail.value.id, side.value);
  const anchor = document.createElement("a");
  anchor.href = `${import.meta.env.VITE_APP_BASE_API}/system/http-log/file/${response.data.data.ticket}`;
  anchor.download = "";
  anchor.click();
}
onMounted(async () => {
  months.value = (await HttpLogAPI.months()).data.data;
  await loadRows();
});
</script>
<style scoped>
.http-log-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 55vh;
  overflow: auto;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}
</style>
