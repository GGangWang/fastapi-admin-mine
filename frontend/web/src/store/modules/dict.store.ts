import { defineStore } from "pinia";
import { computed, ref } from "vue";
import DictAPI, { type DictDataTable } from "@/api/module_system/dict";
import { store } from "@stores";
export type DictMode = "flat" | "tree";
export const useDictStore = defineStore(
  "dictStoreV4",
  () => {
    const dictData = ref<Record<string, DictDataTable[]>>({});
    const fetchedAt = ref<Record<string, number>>({});
    const revision = ref(0);
    const pending = new Map<string, Promise<void>>();
    let generation = 0;
    const key = (type: string, mode: DictMode) => (mode === "flat" ? type : `tree:${type}`);
    async function getDict(types: string[], mode: DictMode = "flat", force = false) {
      const unique = [...new Set(types)];
      const missing = unique.filter(
        (type) =>
          !pending.has(key(type, mode)) &&
          (force ||
            !Object.hasOwn(dictData.value, key(type, mode)) ||
            Date.now() - (fetchedAt.value[key(type, mode)] ?? 0) >= 30000)
      );
      if (missing.length) {
        const version = generation;
        const task = DictAPI.getTypes(missing, mode)
          .then((response) => {
            if (version !== generation) return;
            for (const type of missing) {
              dictData.value[key(type, mode)] = response.data.data[type] ?? [];
              fetchedAt.value[key(type, mode)] = Date.now();
            }
          })
          .finally(() => {
            for (const type of missing)
              if (pending.get(key(type, mode)) === task) pending.delete(key(type, mode));
          });
        for (const type of missing) pending.set(key(type, mode), task);
      }
      await Promise.all(unique.map((type) => pending.get(key(type, mode))));
      return Object.fromEntries(
        unique.map((type) => [type, dictData.value[key(type, mode)] ?? []])
      );
    }
    function clearDictData() {
      generation++;
      pending.clear();
      dictData.value = {};
      fetchedAt.value = {};
      revision.value++;
    }
    const getDictArray = (type: string, mode: DictMode = "flat") =>
      (dictData.value[key(type, mode)] ?? []) as Array<
        DictDataTable & { dict_label: string; dict_value: string }
      >;
    const getDictLabel = (type: string, value: unknown) =>
      getDictArray(type).find((item) => String(item.dict_value) === String(value)) ??
      String(value ?? "");
    return {
      dictData,
      fetchedAt,
      revision,
      getDict,
      getDictArray,
      getDictLabel,
      clearDictData,
      getDictData: computed(() => dictData.value),
      isLoaded: computed(() => Object.keys(fetchedAt.value).length > 0),
    };
  },
  { persist: { pick: ["dictData", "fetchedAt"] } }
);
export function useDictStoreHook() {
  return useDictStore(store);
}
