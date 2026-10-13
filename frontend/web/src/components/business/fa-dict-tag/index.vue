<template>
  <template v-for="(entry, index) in entries" :key="index">
    <span v-if="text || !entry.item?.list_class" :class="entry.item?.css_class">{{
      entry.label
    }}</span>
    <ElTag v-else :type="tagType(entry.item.list_class)" :class="entry.item.css_class">{{
      entry.label
    }}</ElTag>
    <span v-if="index < entries.length - 1">{{ separator }}</span>
  </template>
</template>
<script setup lang="ts">
import { computed } from "vue";
import { useDictStore } from "@stores";
import { dictOptions, resolveDict } from "@/utils/dict";
const props = withDefaults(
  defineProps<{
    type: string;
    value?: unknown;
    text?: boolean;
    cascader?: boolean;
    separator?: string;
  }>(),
  { separator: ", " }
);
const store = useDictStore();
const entries = computed(() =>
  resolveDict(
    dictOptions(store.getDictArray(props.type, props.cascader ? "tree" : "flat")),
    props.value,
    props.cascader
  )
);
function tagType(value: string) {
  return (["primary", "success", "info", "warning", "danger"].includes(value) ? value : "info") as
    | "primary"
    | "success"
    | "info"
    | "warning"
    | "danger";
}
</script>
