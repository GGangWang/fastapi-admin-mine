import { DictTypeEnum } from "@/constants/dict-types";
import type { DictDataTable } from "@/api/module_system/dict";
export type DictValueType = "string" | "number" | "boolean";
export interface DictOption {
  id?: string | number;
  value: string;
  label: string;
  disabled: boolean;
  list_class?: string;
  css_class?: string;
  is_default?: boolean;
  children?: DictOption[];
}
export function dictOptions(rows: DictDataTable[]): DictOption[] {
  const result: DictOption[] = [];
  const work = [{ rows, target: result }];
  while (work.length) {
    const { rows, target } = work.pop()!;
    for (const row of rows) {
      const item: DictOption = {
        id: row.id,
        value: String(row.dict_value ?? row.dict_code ?? ""),
        label: row.dict_label ?? row.dict_name ?? "",
        disabled: row.status === 1,
        list_class: row.list_class,
        css_class: row.css_class,
        is_default: row.is_default,
      };
      target.push(item);
      if (row.children) {
        item.children = [];
        work.push({ rows: row.children, target: item.children });
      }
    }
  }
  return result;
}
export function convertDictValue(value: string, type: DictValueType): string | number | boolean {
  if (type === "string") return value;
  if (type === "boolean") {
    if (value === "true") return true;
    if (value === "false") return false;
    throw new Error(`Invalid boolean dictionary value: ${value}`);
  }
  if (value.trim() === "" || !Number.isFinite(Number(value)))
    throw new Error(`Invalid numeric dictionary value: ${value}`);
  return Number(value);
}
export function resolveDict(
  options: DictOption[],
  value: unknown,
  cascader = false
): Array<{ label: string; item?: DictOption }> {
  if (value === null || value === undefined || value === "") return [];
  if (cascader) {
    const paths =
      Array.isArray(value) && Array.isArray(value[0])
        ? value
        : [Array.isArray(value) ? value : [value]];
    return paths.map((path) => {
      let children = options;
      let item: DictOption | undefined;
      const labels: string[] = [];
      for (const code of path) {
        item = children.find(
          (option) => option.value === String(code) || String(option.id) === String(code)
        );
        labels.push(item?.label ?? String(code));
        children = item?.children ?? [];
      }
      return { label: labels.join(" / "), item };
    });
  }
  return (Array.isArray(value) ? value : [value]).map((code) => {
    const item = options.find((option) => option.value === String(code));
    return { label: item?.label ?? String(code), item };
  });
}
export function transformDict(options: DictOption[], value: unknown, cascader = false) {
  return resolveDict(options, value, cascader)
    .map((item) => item.label)
    .join(", ");
}

/** Metadata-driven generator dictionaries may be registered after the framework ships. */
export function resolveDictType(code: string): string {
  return Object.values(DictTypeEnum).find((value) => value === code) ?? code;
}
