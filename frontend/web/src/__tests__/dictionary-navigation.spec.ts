import FaButtonTable from "@/components/forms/fa-button-table/index.vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { computed, defineComponent, h } from "vue";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { createPinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { createI18n } from "vue-i18n";
import ElementPlus from "element-plus";
import zh from "@/locales/langs/zh.json";
import DictionaryPage from "@/views/module_system/dict/index.vue";
import FaTable from "@/components/tables/fa-table/index.vue";

const api = vi.hoisted(() => ({ listNodes: vi.fn(), ancestors: vi.fn() }));
vi.mock("@/api/module_system/dict", () => ({ default: api }));
vi.mock("@stores", async () => {
  const { defineStore } = await import("pinia");
  const useTableStore = defineStore("dictionary-test-table", {
    state: () => ({
      isBorder: false,
      isZebra: false,
      tableSize: "default",
      isFullScreen: false,
      isHeaderBackground: false,
      isRowDrag: false,
      highlightCurrentRow: false,
    }),
  });
  return {
    useTableStore,
    useDictStore: () => ({
      clearDictData: vi.fn(),
      getDict: vi.fn().mockResolvedValue({}),
      getDictArray: () => [],
      revision: 0,
    }),
  };
});
vi.mock("@/hooks/core/useCommon", () => ({ useCommon: () => ({ scrollToTop: vi.fn() }) }));
vi.mock("@/hooks/core/useTableHeight", () => ({ useTableHeight: vi.fn() }));
vi.mock("vue-draggable-plus", () => ({
  VueDraggable: defineComponent({
    setup(_, { slots }) {
      return () => h("div", slots.default?.());
    },
  }),
}));

const root = {
  id: 1,
  parent_id: null,
  dict_name: "测试分类",
  dict_code: "test_category",
  dict_type: "test_category",
  dict_level: 0,
  dict_sort: 0,
  status: 0,
  is_default: false,
  source: "database",
  readonly: false,
  has_children: true,
  description: "分类备注",
};
const child = {
  ...root,
  id: 2,
  parent_id: 1,
  dict_name: "一级选项",
  dict_code: "001",
  dict_level: 1,
};
const leaf = {
  ...child,
  id: 3,
  parent_id: 2,
  dict_name: "末级选项",
  dict_code: "002",
  dict_level: 2,
  has_children: false,
};
const enumRoot = {
  ...root,
  id: "enum:test_status",
  dict_name: "枚举类型",
  dict_code: "test_status",
  dict_type: "test_status",
  source: "enum",
  readonly: true,
};
const enumChild = {
  ...enumRoot,
  id: "enum:test_status:child",
  parent_id: enumRoot.id,
  dict_name: "枚举选项",
  dict_code: "0",
  dict_level: 1,
  has_children: false,
};
let wrapper: VueWrapper | undefined;

beforeEach(() => {
  vi.stubGlobal("computed", computed);
  vi.stubGlobal("useResizeObserver", vi.fn());
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  );
  api.listNodes.mockImplementation(async (query) => {
    const parent = String(query.parent_id ?? "");
    const items =
      parent === "1"
        ? [child]
        : parent === "2"
          ? [leaf]
          : parent === enumRoot.id
            ? [enumChild]
            : parent
              ? []
              : [root, enumRoot];
    return { data: { data: { items, total: items.length } } };
  });
  api.ancestors.mockImplementation(async (id) => ({
    data: {
      data:
        String(id) === "1"
          ? [root]
          : String(id) === "2"
            ? [root, child]
            : String(id) === "3"
              ? [root, child, leaf]
              : String(id) === enumRoot.id
                ? [enumRoot]
                : [enumRoot, enumChild],
    },
  }));
});
afterEach(() => {
  wrapper?.unmount();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

async function setup() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/system/dict", component: DictionaryPage }],
  });
  await router.push("/system/dict");
  await router.isReady();
  wrapper = mount(DictionaryPage, {
    attachTo: document.body,
    global: {
      plugins: [
        createPinia(),
        router,
        createI18n({ legacy: false, locale: "zh", messages: { zh } }),
        ElementPlus,
      ],
      components: { FaTable, FaButtonTable },
      directives: { hasPerm: {} },
      stubs: {
        FaTableHeader: { template: '<div><slot name="left" /></div>' },
        FaTableHeaderLeft: { template: "<div><slot /></div>" },
        FaSearchBar: true,
        FaForm: true,
        FaDialog: true,
        FaPagination: true,
        FaSvgIcon: true,
      },
    },
  });
  await flushPromises();
  return router;
}
async function click(text: string, index = 0) {
  const buttons = wrapper!
    .findAll("button, [role=button]")
    .filter((button) => (button.attributes("aria-label") ?? button.text()) === text);
  expect(buttons.length).toBeGreaterThan(index);
  await buttons[index]!.trigger("click");
  await flushPromises();
}

describe("字典页面与真实 FaTable 接入", () => {
  it("渲染操作与普通列，并逐级进入、返回及打开空子级", async () => {
    const router = await setup();
    expect(wrapper!.findComponent(FaTable).exists()).toBe(true);
    expect(wrapper!.text()).toContain("test_category");
    expect(wrapper!.text()).toContain("分类备注");
    expect(wrapper!.text()).toContain("测试分类");
    await click("编辑下级");
    expect(router.currentRoute.value.query.parent).toBe("1");
    expect(api.listNodes).toHaveBeenLastCalledWith(
      expect.objectContaining({ parent_id: "1", page_no: 1 })
    );
    expect(api.ancestors).toHaveBeenLastCalledWith("1");
    expect(wrapper!.text()).toContain("一级选项");
    await click("编辑下级");
    expect(router.currentRoute.value.query.parent).toBe("2");
    expect(wrapper!.text()).toContain("末级选项");
    await click("编辑下级");
    expect(router.currentRoute.value.query.parent).toBe("3");
    expect(
      wrapper!
        .findAll("button, [role=button]")
        .filter((button) => button.attributes("aria-label") === "编辑下级")
    ).toHaveLength(0);
    await click("返回上级");
    expect(router.currentRoute.value.query.parent).toBe("2");
    await click("返回上级");
    await click("返回上级");
    expect(router.currentRoute.value.query.parent).toBeUndefined();
  });

  it("支持枚举字符串节点导航，并保持枚举子级只读", async () => {
    const router = await setup();
    await click("编辑下级", 1);
    expect(router.currentRoute.value.query.parent).toBe(enumRoot.id);
    expect(api.ancestors).toHaveBeenLastCalledWith(enumRoot.id);
    expect(wrapper!.text()).toContain("枚举选项");
    for (const label of ["新增", "编辑", "删除"]) {
      expect(
        wrapper!
          .findAll("button, [role=button]")
          .filter((button) => (button.attributes("aria-label") ?? button.text()) === label)
      ).toHaveLength(0);
    }
    await click("返回上级");
    expect(router.currentRoute.value.query.parent).toBeUndefined();
  });
});
