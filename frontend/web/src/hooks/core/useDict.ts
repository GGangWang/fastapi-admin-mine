import { computed, ref, reactive, watchEffect, watch, onActivated, onDeactivated } from "vue";
import { useDictStore } from "@stores";
import { dictOptions, convertDictValue, transformDict, type DictValueType } from "@/utils/dict";
import type { DictMode } from "@/store/modules/dict.store";
export function useDict(types: readonly string[], config: { mode?: DictMode } = {}) {
  const store = useDictStore();
  const mode = config.mode ?? "flat";
  const loading = ref(false);
  const error = ref<unknown>();
  let active = true;
  let sequence = 0;
  async function load(force = false) {
    const current = ++sequence;
    loading.value = true;
    error.value = undefined;
    try {
      await store.getDict([...types], mode, force);
    } catch (cause) {
      if (current === sequence) error.value = cause;
    } finally {
      if (current === sequence) loading.value = false;
    }
  }
  const ready = load();
  onDeactivated(() => {
    active = false;
  });
  onActivated(() => {
    active = true;
    void load();
  });
  watch(
    () => store.revision,
    () => {
      if (active) void load();
    }
  );
  const data = computed(() =>
    Object.fromEntries(types.map((type) => [type, dictOptions(store.getDictArray(type, mode))]))
  );
  const converted = new Map<
    string,
    Array<Partial<import("@/utils/dict").DictOption> & { label: string; value: any }>
  >();
  function options(type: string, valueType: DictValueType = "string") {
    const key = `${type}:${valueType}`;
    if (!converted.has(key)) {
      const result = reactive<
        Array<Partial<import("@/utils/dict").DictOption> & { label: string; value: any }>
      >([]);
      converted.set(key, result);
      watchEffect(() => {
        result.splice(
          0,
          result.length,
          ...(data.value[type] ?? []).map((item) => ({
            ...item,
            value: convertDictValue(item.value, valueType),
          }))
        );
      });
    }
    return converted.get(key)!;
  }
  const tags = new Map<
    string,
    Record<string, { type: "primary" | "success" | "warning" | "info" | "danger"; text: string }>
  >();
  function tagMap(type: string) {
    if (tags.has(type)) return tags.get(type)!;
    const result = reactive<
      Record<string, { type: "primary" | "success" | "warning" | "info" | "danger"; text: string }>
    >({});
    watchEffect(() => {
      for (const key of Object.keys(result)) delete result[key];
      for (const item of data.value[type] ?? [])
        result[item.value] = {
          type: (["primary", "success", "warning", "info", "danger"].includes(item.list_class ?? "")
            ? item.list_class
            : "info") as "primary" | "success" | "warning" | "info" | "danger",
          text: item.label,
        };
    });
    tags.set(type, result);
    return result;
  }
  const label = (type: string, value: unknown, cascader = false) =>
    transformDict(data.value[type] ?? [], value, cascader);
  return { data, loading, error, ready, options, tagMap, label, reload: () => load(true) };
}
