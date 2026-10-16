import { mount, flushPromises } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { createI18n } from "vue-i18n";
import { describe, expect, it, vi } from "vitest";
import { beijingTime } from "@/utils/dateTime";
import zh from "@/locales/langs/zh.json";
import HttpLogPage from "@/views/module_system/http_log/index.vue";

const api = vi.hoisted(() => ({
  months: vi.fn(),
  list: vi.fn(),
  detail: vi.fn(),
  body: vi.fn(),
  ticket: vi.fn(),
}));
vi.mock("@/api/module_system/http-log", () => ({ default: api }));
vi.mock("@/hooks/core/useDict", () => ({ useDict: () => ({ options: () => [] }) }));

const row = {
  id: "a".repeat(32),
  method: "GET",
  result: "success",
  request_body_state: "recorded",
  response_body_state: "not_recorded",
};
const table = defineComponent({
  props: ["data"],
  setup(props, { slots }) {
    return () =>
      h(
        "div",
        props.data?.map((item: unknown) => slots.actions?.({ row: item }))
      );
  },
});
const button = defineComponent({
  setup(_, { emit }) {
    return () => h("button", { "data-test": "detail", onClick: () => emit("click") }, "详情");
  },
});

describe("HTTP log management", () => {
  it("queries one month and loads body only after user action", async () => {
    const month = beijingTime().format("YYYYMM");
    api.months.mockResolvedValue({ data: { data: [month] } });
    api.list.mockResolvedValue({ data: { data: { items: [row], total: 1 } } });
    api.detail.mockResolvedValue({ data: { data: row } });
    api.body.mockResolvedValue({
      data: {
        data: {
          text: '{"token":"original"}',
          offset: 0,
          next_offset: 20,
          total_bytes: 20,
          has_next: false,
          state: "recorded",
        },
      },
    });
    const wrapper = mount(HttpLogPage, {
      global: {
        plugins: [createI18n({ legacy: false, locale: "zh", messages: { zh } })],
        directives: { hasPerm: () => {}, loading: () => {} },
        stubs: {
          FaSearchBar: defineComponent({ name: "FaSearchBar", props: ["modelValue", "items"], emits: ["update:modelValue", "search"], setup: () => () => h("div") }),
          FaTable: table,
          FaButtonTable: button,
          FaDictTag: true,
          FaTableHeader: { template: '<div><slot name="left" /></div>' },
          ElCard: { template: "<div><slot /></div>" },
          ElTooltip: { template: "<div><slot /></div>" },
          ElDrawer: { template: "<div><slot /></div>" },
          ElDescriptions: { template: "<div><slot /></div>" },
          ElDescriptionsItem: { template: "<div><slot /></div>" },
          ElTabs: { template: "<div><slot /></div>" },
          ElTabPane: true,
          ElSelect: true,
          ElOption: true,
          ElTag: { template: "<span><slot /></span>" },
          ElButton: { template: "<button @click=\"$emit('click')\"><slot /></button>" },
        },
      },
    });
    await flushPromises();
    expect(api.list).toHaveBeenCalledWith(expect.objectContaining({ month }));
    const searchBar = wrapper.findComponent({ name: "FaSearchBar" });
    const fields = searchBar.props("items") as Array<{
      key: string;
      props?: { valueFormat?: string };
    }>;
    expect(fields.find((item) => item.key === "start_time")?.props?.valueFormat).toBe(
      "YYYY-MM-DD HH:mm:ss"
    );
    const start = `${month.slice(0, 4)}-${month.slice(4)}-01 00:00:00`;
    searchBar.vm.$emit("update:modelValue", { start_time: start });
    await wrapper.vm.$nextTick();
    searchBar.vm.$emit("search");
    await flushPromises();
    expect(api.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ start_time: start, month })
    );
    expect(api.body).not.toHaveBeenCalled();
    await wrapper.get('[data-test="detail"]').trigger("click");
    await flushPromises();
    expect(api.detail).toHaveBeenCalledWith(month, row.id);
    expect(api.body).not.toHaveBeenCalled();
    const load = wrapper.findAll("button").find((item) => item.text() === "读取正文")!;
    await load.trigger("click");
    await flushPromises();
    expect(api.body).toHaveBeenCalledWith(month, row.id, "request", 0);
    expect(wrapper.text()).toContain('"token":"original"');
    wrapper.unmount();
  });
});
