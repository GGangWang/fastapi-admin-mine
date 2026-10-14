import { mount, flushPromises } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { createI18n } from "vue-i18n";
import { describe, expect, it, vi } from "vitest";
import zh from "@/locales/langs/zh.json";
import HttpLogPage from "@/views/module_system/http_log/index.vue";

const api = vi.hoisted(() => ({ months: vi.fn(), list: vi.fn(), detail: vi.fn(), body: vi.fn(), ticket: vi.fn() }));
vi.mock("@/api/module_system/http-log", () => ({ default: api }));
vi.mock("@/hooks/core/useDict", () => ({ useDict: () => ({ options: () => [] }) }));

const row = { id: "a".repeat(32), method: "GET", result: "success", request_body_state: "recorded", response_body_state: "not_recorded" };
const table = defineComponent({
  props: ["data"],
  setup(props, { slots }) { return () => h("div", props.data?.map((item: unknown) => slots.actions?.({ row: item }))); },
});
const button = defineComponent({ setup(_, { emit }) { return () => h("button", { "data-test": "detail", onClick: () => emit("click") }, "详情"); } });

describe("HTTP log management", () => {
  it("queries one month and loads body only after user action", async () => {
    const now = new Date();
    const month = `${now.getFullYear()}${String(now.getMonth()+1).padStart(2,"0")}`;
    api.months.mockResolvedValue({ data: { data: [month] } });
    api.list.mockResolvedValue({ data: { data: { items: [row], total: 1 } } });
    api.detail.mockResolvedValue({ data: { data: row } });
    api.body.mockResolvedValue({ data: { data: { text: '{"token":"original"}', offset: 0, next_offset: 20, total_bytes: 20, has_next: false, state: "recorded" } } });
    const wrapper = mount(HttpLogPage, { global: {
      plugins: [createI18n({ legacy: false, locale: "zh", messages: { zh } })],
      directives: { hasPerm: () => {} },
      stubs: {
        FaSearchBar: true, FaTable: table, FaButtonTable: button, FaDictTag: true,
        FaTableHeader: { template: '<div><slot name="left" /></div>' },
        ElCard: { template: '<div><slot /></div>' },
        ElTooltip: { template: '<div><slot /></div>' },
        ElDrawer: { template: '<div><slot /></div>' },
        ElDescriptions: { template: '<div><slot /></div>' },
        ElDescriptionsItem: { template: '<div><slot /></div>' },
        ElTabs: { template: '<div><slot /></div>' }, ElTabPane: true,
        ElSelect: true, ElOption: true, ElTag: { template: '<span><slot /></span>' },
        ElButton: { template: '<button @click="$emit(\'click\')"><slot /></button>' },
      },
    } });
    await flushPromises();
    expect(api.list).toHaveBeenCalledWith(expect.objectContaining({ month }));
    expect(api.body).not.toHaveBeenCalled();
    await wrapper.get('[data-test="detail"]').trigger("click");
    await flushPromises();
    expect(api.detail).toHaveBeenCalledWith(month, row.id);
    expect(api.body).not.toHaveBeenCalled();
    const load = wrapper.findAll("button").find(item => item.text() === "读取正文")!;
    await load.trigger("click"); await flushPromises();
    expect(api.body).toHaveBeenCalledWith(month, row.id, "request", 0);
    expect(wrapper.text()).toContain('"token":"original"');
    wrapper.unmount();
  });
});
