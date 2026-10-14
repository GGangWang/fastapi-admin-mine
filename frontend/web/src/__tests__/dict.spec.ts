import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { defineComponent, h, nextTick } from "vue";
import { mount, flushPromises } from "@vue/test-utils";
import { useDictStore } from "@/store/modules/dict.store";
import { useDict } from "@/hooks/core/useDict";
import { convertDictValue, dictOptions, transformDict } from "@/utils/dict";
import FaDictTag from "@/components/business/fa-dict-tag/index.vue";
const api = vi.hoisted(() => ({ getTypes: vi.fn() }));
vi.mock("@/api/module_system/dict", () => ({ default: api }));
vi.mock("@stores", () => ({
  store: undefined,
  useDictStore: (...args: any[]) => useDictStore(...args),
}));
const row = (value = "1", label = "启用") => ({
  dict_value: value,
  dict_label: label,
  status: 1,
  list_class: "success",
});
beforeEach(() => {
  setActivePinia(createPinia());
  api.getTypes.mockReset();
  api.getTypes.mockImplementation(async (types: string[]) => ({
    data: { data: Object.fromEntries(types.map((type) => [type, [row()]])) },
  }));
});
describe("字典批量缓存", () => {
  it("批量去重、空数组缓存、过期刷新及树隔离", async () => {
    const store = useDictStore();
    api.getTypes.mockResolvedValueOnce({ data: { data: { a: [row()], b: [] } } });
    await store.getDict(["a", "b", "a"]);
    expect(api.getTypes).toHaveBeenCalledWith(["a", "b"], "flat");
    await store.getDict(["a", "b"]);
    expect(api.getTypes).toHaveBeenCalledTimes(1);
    store.fetchedAt.a = Date.now() - 31000;
    await store.getDict(["a", "b"]);
    expect(api.getTypes).toHaveBeenLastCalledWith(["a"], "flat");
    await store.getDict(["a"], "tree");
    expect(api.getTypes).toHaveBeenLastCalledWith(["a"], "tree");
  });
  it("重叠请求复用，清理后忽略旧响应", async () => {
    const store = useDictStore();
    let resolve!: (value: any) => void;
    api.getTypes.mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done;
        })
    );
    const first = store.getDict(["a", "b"]);
    const second = store.getDict(["b", "c"]);
    expect(api.getTypes.mock.calls.map((call) => call[0])).toEqual([["a", "b"], ["c"]]);
    store.clearDictData();
    resolve({ data: { data: { a: [row()], b: [row()] } } });
    await Promise.all([first, second]);
    expect(store.dictData).toEqual({});
  });
  it("失败保留数据并允许重试", async () => {
    const store = useDictStore();
    await store.getDict(["a"]);
    api.getTypes.mockRejectedValueOnce(new Error("offline"));
    await expect(store.getDict(["a"], "flat", true)).rejects.toThrow("offline");
    expect(store.getDictArray("a")[0]?.dict_value).toBe("1");
    await store.getDict(["a"], "flat", true);
    expect(api.getTypes).toHaveBeenCalledTimes(3);
  });
  it("页面选项与标签在刷新后同步更新", async () => {
    let dictionary!: ReturnType<typeof useDict>;
    const wrapper = mount(
      defineComponent({
        setup() {
          dictionary = useDict(["a", "b"]);
          const options = dictionary.options("a", "number");
          return () => h("div", `${options[0]?.value}:${dictionary.label("a", 1)}`);
        },
      })
    );
    await dictionary.ready;
    await nextTick();
    expect(wrapper.text()).toBe("1:启用");
    api.getTypes.mockImplementation(async () => ({
      data: { data: { a: [row("1", "新标签")], b: [] } },
    }));
    useDictStore().clearDictData();
    await flushPromises();
    expect(wrapper.text()).toBe("1:新标签");
    wrapper.unmount();
  });
});
describe("字典转换与组件", () => {
  it("严格处理数字、布尔及未知值", () => {
    expect(convertDictValue("0", "number")).toBe(0);
    expect(convertDictValue("false", "boolean")).toBe(false);
    expect(() => convertDictValue("0", "boolean")).toThrow();
    expect(() => convertDictValue("", "number")).toThrow();
    const options = dictOptions([row("false", "否"), row("0", "零")]);
    expect(transformDict(options, false)).toBe("否");
    expect(transformDict(options, 0)).toBe("零");
    expect(transformDict(options, [false, "other"])).toBe("否, other");
    expect(transformDict(options, null)).toBe("");
  });
  it("级联按完整路径区分重复值并支持深层级", () => {
    const options = dictOptions([
      { dict_code: "a", dict_name: "A", children: [{ dict_code: "same", dict_name: "甲" }] },
      { dict_code: "b", dict_name: "B", children: [{ dict_code: "same", dict_name: "乙" }] },
    ]);
    expect(transformDict(options, ["a", "same"], true)).toBe("A / 甲");
    expect(
      transformDict(
        options,
        [
          ["b", "same"],
          ["a", "same"],
        ],
        true
      )
    ).toBe("B / 乙, A / 甲");
    let tree: any[] = [];
    let cursor = tree;
    for (let i = 0; i < 2000; i++) {
      const node = { dict_code: String(i), dict_name: String(i), children: [] };
      cursor.push(node);
      cursor = node.children;
    }
    expect(
      transformDict(
        dictOptions(tree),
        Array.from({ length: 2000 }, (_, i) => String(i)),
        true
      ).split(" / ")
    ).toHaveLength(2000);
  });
  it("标签组件不发请求，支持样式、文本及原值回显", async () => {
    useDictStore().dictData.a = [row()];
    const wrapper = mount(FaDictTag, {
      props: { type: "a", value: 1 },
      global: {
        stubs: { ElTag: { props: ["type"], template: '<span :data-type="type"><slot /></span>' } },
      },
    });
    expect(wrapper.text()).toBe("启用");
    expect(wrapper.find("span").attributes("data-type")).toBe("success");
    await wrapper.setProps({ value: "missing", text: true });
    expect(wrapper.text()).toBe("missing");
    expect(api.getTypes).not.toHaveBeenCalled();
  });
});
