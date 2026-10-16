import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { defineComponent, h, KeepAlive, nextTick, ref } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import Page from "@/views/module_demo/test_validation/index.vue";
const calls = vi.hoisted(() => ({
  create: vi.fn(),
  refresh: vi.fn(),
  playback: vi.fn(),
  destroy: vi.fn(),
  rebuild: vi.fn(),
}));
vi.mock("vue-i18n", async () => {
  const { ref } = await import("vue");
  return { useI18n: () => ({ t: (key: string) => key, locale: ref("zh") }) };
});
vi.mock("@/views/module_demo/test_validation/renderer", () => ({
  TopologyRenderer: class {
    constructor() {
      calls.create();
    }
    refresh() {
      calls.refresh();
      return Promise.resolve();
    }
    setPlayback(...args: unknown[]) {
      calls.playback(...args);
      return Promise.resolve();
    }
    rebuild() {
      calls.rebuild();
      return Promise.resolve();
    }
    resize() {}
    destroy() {
      calls.destroy();
    }
  },
}));
const stubs = Object.fromEntries(
  ["ElTag", "ElSelect", "ElOption", "ElSwitch", "ElButton", "ElAlert"].map((key) => [key, true])
);
beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  Object.defineProperty(document, "hidden", { configurable: true, value: false });
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    }
  );
  vi.stubGlobal("cancelAnimationFrame", vi.fn());
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
describe("test validation graph lifecycle", () => {
  it("does not start playback when deactivated before the lazy renderer loads", async () => {
    const shown = ref(true);
    const Host = defineComponent({
      setup: () => () => h(KeepAlive, null, () => (shown.value ? h(Page) : null)),
    });
    const wrapper = mount(Host, { global: { stubs, directives: { loading: () => {} } } });
    shown.value = false;
    await nextTick();
    await flushPromises();
    expect(calls.create).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(2000);
    expect(calls.refresh).not.toHaveBeenCalled();
    shown.value = true;
    await nextTick();
    await flushPromises();
    expect(calls.create).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(calls.refresh).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("pauses cached pages and resumes a single existing renderer", async () => {
    const shown = ref(true);
    const Host = defineComponent({
      setup: () => () => h(KeepAlive, null, () => (shown.value ? h(Page) : null)),
    });
    const wrapper = mount(Host, { global: { stubs, directives: { loading: () => {} } } });
    await flushPromises();
    expect(calls.create).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(calls.refresh).toHaveBeenCalledTimes(1);
    shown.value = false;
    await nextTick();
    const count = calls.refresh.mock.calls.length;
    await vi.advanceTimersByTimeAsync(3000);
    expect(calls.refresh).toHaveBeenCalledTimes(count);
    expect(calls.playback).toHaveBeenLastCalledWith(false, true);
    shown.value = true;
    await nextTick();
    await flushPromises();
    await vi.advanceTimersByTimeAsync(1000);
    expect(calls.create).toHaveBeenCalledTimes(1);
    expect(calls.refresh).toHaveBeenCalledTimes(count + 1);
    wrapper.unmount();
    expect(calls.destroy).toHaveBeenCalledTimes(1);
    const final = calls.refresh.mock.calls.length;
    await vi.advanceTimersByTimeAsync(2000);
    expect(calls.refresh).toHaveBeenCalledTimes(final);
  });
  it("pauses when the document becomes hidden", async () => {
    const wrapper = mount(Page, { global: { stubs, directives: { loading: () => {} } } });
    await flushPromises();
    Object.defineProperty(document, "hidden", { configurable: true, value: true });
    document.dispatchEvent(new Event("visibilitychange"));
    const count = calls.refresh.mock.calls.length;
    await vi.advanceTimersByTimeAsync(2000);
    expect(calls.refresh).toHaveBeenCalledTimes(count);
    Object.defineProperty(document, "hidden", { configurable: true, value: false });
    document.dispatchEvent(new Event("visibilitychange"));
    await vi.advanceTimersByTimeAsync(1000);
    expect(calls.refresh).toHaveBeenCalledTimes(count + 1);
    wrapper.unmount();
  });
});
