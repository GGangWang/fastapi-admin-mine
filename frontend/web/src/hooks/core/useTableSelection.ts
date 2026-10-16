import type { ComputedRef, Ref } from "vue";

/**
 * 表格多选状态管理
 *
 * @example
 * ```ts
 * const { selectedRows, selectedIds, batchDeleting, onTableSelectionChange } =
 *   useTableSelection<DictTable>();
 * ```
 */
type RowId<T> = T extends { id?: infer Id } ? NonNullable<Id> : number;

export function useTableSelection<T extends object>() {
  const selectedRows = ref<T[]>([]) as Ref<T[]>;
  const selectedIds = computed(() =>
    selectedRows.value
      .map((r) => (r as { id?: RowId<T> }).id)
      .filter((id): id is RowId<T> => id != null && !Number.isNaN(id))
  ) as ComputedRef<RowId<T>[]>;
  const batchDeleting = ref(false);

  function onTableSelectionChange(rows: T[]) {
    selectedRows.value = rows;
  }

  function clearSelection() {
    selectedRows.value = [];
  }

  return {
    selectedRows,
    selectedIds,
    batchDeleting,
    onTableSelectionChange,
    clearSelection,
  };
}
