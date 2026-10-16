<script setup lang="ts">
import {
  computed,
  nextTick,
  onActivated,
  onDeactivated,
  onMounted,
  onUnmounted,
  ref,
  shallowRef,
  watch,
} from "vue";
import { useI18n } from "vue-i18n";
import { ElMessage } from "element-plus";
import {
  campuses,
  generateTopology,
  initialExpansion,
  projectTopology,
  expandGroup,
  updateFlows,
  animationIds,
  formatRate,
  ANIMATION_LIMIT,
} from "./data";
import type { Device, Expansion, ViewNode } from "./data";
import type { TopologyRenderer } from "./renderer";

defineOptions({ name: "TestValidation" });
const { t, locale } = useI18n();
const tr = (key: string) => t(`testValidation.${key}`);
const size = ref(100);
const campus = ref("all");
const topology = shallowRef(generateTopology(size.value));
let expansion: Expansion = initialExpansion(topology.value);
const view = shallowRef(projectTopology(topology.value, expansion));
const canvas = ref<HTMLElement>();
const selectedId = ref("");
const hoveredId = ref("");
const search = ref("");
const searchValue = ref("");
const simulation = ref(true);
const animations = ref(true);
const loading = ref(true);
const error = ref("");
const renderMs = ref(0);
const fps = ref<number>();
const tick = ref(0);
let renderer: TopologyRenderer | undefined;
let initPromise: Promise<void> | undefined;
let interval: ReturnType<typeof setInterval> | undefined;
let observer: ResizeObserver | undefined;
let themeObserver: MutationObserver | undefined;
let active = false;
let disposed = false;
let frame = 0;
let frames = 0;
let frameStart = 0;
function sampleFrames() {
  frames++;
  frame = requestAnimationFrame(sampleFrames);
}
function transform(activeTransform: boolean) {
  if (activeTransform) {
    cancelAnimationFrame(frame);
    frames = 0;
    frameStart = performance.now();
    frame = requestAnimationFrame(sampleFrames);
  } else {
    cancelAnimationFrame(frame);
    const seconds = (performance.now() - frameStart) / 1000;
    if (seconds > 0.2) fps.value = Math.round(frames / seconds);
  }
}
function deviceName(device: Device) {
  return `${device.campusId ? tr(device.campusId) + " · " : ""}${tr(device.kind)} ${String(device.number).padStart(2, "0")} · ${device.id}`;
}
function nodeName(node: ViewNode) {
  if (node.kind === "campus") return tr(node.campusId!);
  if (node.kind === "group") return `${tr("group")} ${node.number}`;
  return `${tr(node.kind)}${node.kind === "service" ? "" : " " + String(node.number).padStart(2, "0")}`;
}
const selectedNode = computed(() => view.value.nodes.find((node) => node.id === selectedId.value));
const selectedEdge = computed(() => view.value.edges.find((edge) => edge.id === selectedId.value));
const relatedEdges = computed(() =>
  view.value.edges.filter(
    (edge) => edge.source === selectedId.value || edge.target === selectedId.value
  )
);
const selectedTotals = computed(() => {
  if (selectedNode.value?.kind === "campus") {
    const campusId = selectedNode.value.campusId;
    const links = topology.value.links.filter(
      (link) =>
        link.source === "service" &&
        topology.value.deviceMap.get(link.target)?.campusId === campusId
    );
    return {
      down: links.reduce((sum, link) => sum + link.down.rate, 0),
      up: links.reduce((sum, link) => sum + link.up.rate, 0),
    };
  }
  const selected = selectedEdge.value;
  const edges = selected
    ? view.value.edges.filter(
        (edge) =>
          (edge.source === selected.source && edge.target === selected.target) ||
          (edge.source === selected.target && edge.target === selected.source)
      )
    : relatedEdges.value;
  return {
    down: edges
      .filter((edge) => edge.direction === "down")
      .reduce((sum, edge) => sum + edge.rate, 0),
    up: edges.filter((edge) => edge.direction === "up").reduce((sum, edge) => sum + edge.rate, 0),
  };
});
const searchResults = computed(() =>
  search.value.trim()
    ? topology.value.devices
        .filter((device) =>
          deviceName(device).toLowerCase().includes(search.value.trim().toLowerCase())
        )
        .slice(0, 30)
    : []
);
const animatedCount = computed(
  () => animationIds(view.value.edges, selectedId.value, animations.value && simulation.value).size
);
const activeCount = computed(
  () => view.value.edges.filter((edge) => edge.state === "active").length
);
const totalUp = computed(() =>
  view.value.edges
    .filter((edge) => edge.direction === "up" && edge.target === "service")
    .reduce((sum, edge) => sum + edge.rate, 0)
);
const hovered = computed(() => {
  const node = view.value.nodes.find((n) => n.id === hoveredId.value);
  if (node) return nodeName(node);
  const edge = view.value.edges.find((e) => e.id === hoveredId.value);
  return edge ? `${tr(edge.direction)} · ${formatRate(edge.rate)} · ${tr(edge.state)}` : "";
});
function fail(reason: unknown) {
  console.error(reason);
  error.value = tr("loadError");
  loading.value = false;
}
function select(id: string) {
  selectedId.value = id;
  void renderer?.refresh(view.value, id);
}
async function redraw(fit = true) {
  view.value = projectTopology(topology.value, expansion, campus.value);
  if (
    selectedId.value &&
    !view.value.nodes.some((node) => node.id === selectedId.value) &&
    !view.value.edges.some((edge) => edge.id === selectedId.value)
  )
    selectedId.value = "";
  await nextTick();
  if (canvas.value) renderer?.resize(canvas.value.clientWidth, canvas.value.clientHeight);
  const start = performance.now();
  await renderer?.rebuild(view.value, fit, selectedId.value);
  renderMs.value = Math.round(performance.now() - start);
}
async function toggle(id = selectedId.value) {
  const node = view.value.nodes.find((n) => n.id === id);
  if (!node) return;
  if (node.kind === "campus") {
    const key = node.campusId!;
    if (expansion.campuses.has(key)) {
      expansion.campuses.delete(key);
      topology.value.groups
        .filter((g) => g.campusId === key)
        .forEach((g) => expansion.groups.delete(g.id));
    } else expansion.campuses.add(key);
  } else if (node.groupId) {
    if (expansion.groups.has(node.groupId)) {
      expansion.groups.delete(node.groupId);
      selectedId.value = node.groupId;
    } else if (!expandGroup(topology.value, expansion, node.groupId)) {
      ElMessage.warning(tr("detailLimit"));
      return;
    }
  } else return;
  await redraw();
}
async function locate(id: string) {
  const device = topology.value.deviceMap.get(id);
  if (!device) return;
  campus.value = device.campusId || "all";
  await nextTick();
  if (device.groupId) expandGroup(topology.value, expansion, device.groupId, true);
  await redraw(false);
  select(id);
  await nextTick();
  if (canvas.value) renderer?.resize(canvas.value.clientWidth, canvas.value.clientHeight);
  await renderer?.focus(id);
}
async function reset() {
  expansion = initialExpansion(topology.value);
  selectedId.value = "";
  searchValue.value = "";
  await redraw();
}
function stop() {
  clearInterval(interval);
  interval = undefined;
  cancelAnimationFrame(frame);
  observer?.disconnect();
  void renderer?.setPlayback(false, animations.value);
}
function start() {
  if (!active || !renderer || document.hidden) return;
  observer?.disconnect();
  observer = new ResizeObserver((entries) => {
    const entry = entries[0];
    if (entry && entry.contentRect.width && entry.contentRect.height)
      renderer?.resize(entry.contentRect.width, entry.contentRect.height);
  });
  if (canvas.value) observer.observe(canvas.value);
  clearInterval(interval);
  void renderer.setPlayback(simulation.value, animations.value);
  interval = setInterval(async () => {
    if (!simulation.value || !active || document.hidden) return;
    updateFlows(topology.value, ++tick.value);
    view.value = projectTopology(topology.value, expansion, campus.value);
    await renderer?.refresh(view.value, selectedId.value);
  }, 1000);
}
async function initialize() {
  if (renderer || disposed || !active) return;
  if (initPromise) return initPromise;
  initPromise = (async () => {
    const started = performance.now();
    try {
      const { TopologyRenderer: Renderer } = await import("./renderer");
      if (disposed || !canvas.value || !active) return;
      renderer = new Renderer(canvas.value, {
        label: nodeName,
        text: tr,
        select,
        toggle: (id) => void toggle(id),
        hover: (id) => {
          hoveredId.value = id;
        },
        error: fail,
        transform,
      });
      await renderer.setPlayback(active && simulation.value && !document.hidden, animations.value);
      await redraw();
      renderMs.value = Math.round(performance.now() - started);
      themeObserver = new MutationObserver(
        () => void renderer?.refresh(view.value, selectedId.value)
      );
      themeObserver.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["class", "style"],
      });
      start();
    } catch (reason) {
      fail(reason);
    } finally {
      loading.value = false;
      if (!renderer) initPromise = undefined;
    }
  })();
  return initPromise;
}
function visibility() {
  if (document.hidden) stop();
  else start();
}
onMounted(() => {
  active = true;
  void initialize();
  document.addEventListener("visibilitychange", visibility);
});
onActivated(() => {
  active = true;
  void initialize().then(start);
});
onDeactivated(() => {
  active = false;
  stop();
});
onUnmounted(() => {
  disposed = true;
  active = false;
  stop();
  renderer?.destroy();
  themeObserver?.disconnect();
  document.removeEventListener("visibilitychange", visibility);
});
watch(size, async () => {
  topology.value = generateTopology(size.value);
  expansion = initialExpansion(topology.value);
  selectedId.value = "";
  campus.value = "all";
  tick.value = 0;
  await redraw();
});
watch(campus, async () => {
  selectedId.value = "";
  await redraw();
});
watch(
  [simulation, animations],
  () => void renderer?.setPlayback(active && simulation.value && !document.hidden, animations.value)
);
watch(locale, () => void renderer?.refresh(view.value, selectedId.value));
</script>

<template>
  <section class="validation-page">
    <header class="heading">
      <div>
        <div class="eyebrow">RESOURCE NETWORK / G6 V5</div>
        <h1>
          {{ tr("title") }} <ElTag size="small" type="warning">{{ tr("mock") }}</ElTag>
        </h1>
        <p>{{ tr("intro") }}</p>
      </div>
      <div class="headline-stats">
        <div>
          <b>{{ topology.devices.length.toLocaleString() }}</b
          ><span>{{ tr("totalDevices") }}</span>
        </div>
        <div>
          <b>{{ view.detailCount }}</b
          ><span>{{ tr("visibleDevices") }}</span>
        </div>
        <div>
          <b class="up-color">{{ formatRate(totalUp) }}</b
          ><span>{{ tr("up") }}</span>
        </div>
      </div>
    </header>
    <div class="toolbar">
      <ElSelect v-model="size" :aria-label="tr('scenario')" style="width: 150px"
        ><ElOption
          v-for="count in [100, 1000, 5000]"
          :key="count"
          :label="`${count.toLocaleString()} ${tr('devices')}`"
          :value="count"
      /></ElSelect>
      <ElSelect v-model="campus" :aria-label="tr('selectCampus')" style="width: 150px"
        ><ElOption value="all" :label="tr('all')" /><ElOption
          v-for="id in campuses"
          :key="id"
          :value="id"
          :label="tr(id)"
      /></ElSelect>
      <ElSelect
        v-model="searchValue"
        filterable
        remote
        clearable
        :remote-method="(value: string) => (search = value)"
        :placeholder="tr('search')"
        :aria-label="tr('search')"
        style="width: 290px"
        @change="(id: string) => locate(id)"
        ><ElOption
          v-for="device in searchResults"
          :key="device.id"
          :label="deviceName(device)"
          :value="device.id"
      /></ElSelect>
      <div class="toolbar-spacer" />
      <ElSwitch v-model="animations" :active-text="tr('flowAnimation')" />
      <ElButton @click="simulation = !simulation">{{
        tr(simulation ? "pause" : "resume")
      }}</ElButton>
      <ElButton @click="reset">{{ tr("reset") }}</ElButton>
    </div>
    <div class="legend">
      <span><i class="down-dot" />{{ tr("down") }}</span
      ><span><i class="up-dot" />{{ tr("up") }}</span
      ><span><i class="offline-dot" />{{ tr("offline") }}</span
      ><span class="legend-hint">{{ tr("expandHint") }}</span>
    </div>
    <ElAlert
      v-if="activeCount > ANIMATION_LIMIT && animations && simulation"
      :title="tr('animationLimit')"
      type="warning"
      :closable="false"
      show-icon
    />
    <div class="workspace" :class="{ 'has-details': selectedNode || selectedEdge }">
      <div class="canvas-shell" v-loading="loading">
        <div ref="canvas" class="graph-canvas" :aria-label="tr('intro')" />
        <div v-if="error" class="graph-error">
          <ElAlert :title="error" type="error" :closable="false" />
        </div>
        <div class="canvas-guide">
          {{ tr("network") }}<small>{{ tr("simulationNote") }}</small>
        </div>
        <div v-if="hovered" class="hover-info">{{ hovered }}</div>
        <div class="canvas-controls">
          <ElButton :aria-label="tr('zoomIn')" @click="renderer?.zoom(1.3)">+</ElButton
          ><ElButton :aria-label="tr('zoomOut')" @click="renderer?.zoom(0.77)">−</ElButton
          ><ElButton @click="renderer?.fit()">{{ tr("fit") }}</ElButton>
        </div>
        <div class="performance">
          {{ simulation ? tr("simulating") : tr("paused") }} · {{ animatedCount }}/{{ activeCount }}
          {{ tr("animatedLinks") }} · {{ renderMs }} ms<span v-if="fps !== undefined">
            · {{ fps }} FPS</span
          >
        </div>
      </div>
      <aside v-if="selectedNode || selectedEdge" class="details">
        <div class="details-heading">
          <h2>{{ tr(selectedEdge ? "linkDetails" : "details") }}</h2>
          <ElButton text :aria-label="tr('close')" @click="select('')">×</ElButton>
        </div>
        <template v-if="selectedNode"
          ><h3>{{ nodeName(selectedNode) }}</h3>
          <ElTag size="small">{{ tr(selectedNode.kind) }}</ElTag>
          <dl>
            <dt>{{ tr("campus") }}</dt>
            <dd>{{ selectedNode.campusId ? tr(selectedNode.campusId) : tr("shared") }}</dd>
            <dt>{{ tr("online") }} / {{ tr("devices") }}</dt>
            <dd>{{ selectedNode.online }} / {{ selectedNode.count }}</dd>
          </dl>
          <ElButton v-if="selectedNode.campusId" @click="toggle()">{{
            tr(
              selectedNode.kind === "campus"
                ? expansion.campuses.has(selectedNode.campusId)
                  ? "collapse"
                  : "expand"
                : selectedNode.groupId && expansion.groups.has(selectedNode.groupId)
                  ? "collapseGroup"
                  : "expand"
            )
          }}</ElButton></template
        >
        <template v-if="selectedEdge"
          ><h3>{{ tr(selectedEdge.direction) }}</h3>
          <dl>
            <dt>{{ tr("source") }}</dt>
            <dd>{{ nodeName(view.nodes.find((n) => n.id === selectedEdge!.source)!) }}</dd>
            <dt>{{ tr("destination") }}</dt>
            <dd>{{ nodeName(view.nodes.find((n) => n.id === selectedEdge!.target)!) }}</dd>
            <dt>{{ tr("status") }}</dt>
            <dd>{{ tr(selectedEdge.state) }}</dd>
            <dt>{{ tr("members") }}</dt>
            <dd>{{ selectedEdge.members.length }}</dd>
          </dl></template
        >
        <div class="rate-card down">
          <span>{{ tr("down") }}</span
          ><b>{{ formatRate(selectedTotals.down) }}</b>
        </div>
        <div class="rate-card up">
          <span>{{ tr("up") }}</span
          ><b>{{ formatRate(selectedTotals.up) }}</b>
        </div>
        <p class="muted">{{ tr("simulationNote") }}</p>
        <h4>{{ tr("related") }}</h4>
        <button
          v-for="edge in relatedEdges.slice(0, 40)"
          :key="edge.id"
          class="related-item"
          @click="select(edge.id)"
        >
          <span>{{ tr(edge.direction) }} · {{ tr(edge.state) }}</span
          ><b>{{ formatRate(edge.rate) }}</b>
        </button>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.validation-page {
  padding: 22px;
  color: var(--el-text-color-primary);
}
.heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
  margin-bottom: 22px;
}
.eyebrow {
  font-size: 10px;
  letter-spacing: 2px;
  color: var(--el-color-primary);
  font-weight: 700;
  margin-bottom: 10px;
}
h1 {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 24px;
  font-weight: 650;
}
.heading p {
  margin: 9px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.headline-stats {
  display: flex;
  gap: 32px;
}
.headline-stats div {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.headline-stats b {
  font-size: 22px;
  font-variant-numeric: tabular-nums;
}
.headline-stats span {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.up-color {
  color: #0d9488;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 14px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
}
.toolbar-spacer {
  flex: 1;
}
.toolbar :deep(.el-button + .el-button) {
  margin-left: 0;
}
.legend {
  display: flex;
  align-items: center;
  gap: 24px;
  font-size: 12px;
  padding: 16px 2px;
  color: var(--el-text-color-secondary);
  flex-wrap: wrap;
}
.legend span {
  display: flex;
  align-items: center;
  gap: 7px;
}
.legend i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.down-dot {
  background: #6366f1;
}
.up-dot {
  background: #0d9488;
}
.offline-dot {
  background: #94a3b8;
}
.legend-hint {
  margin-left: auto;
}
.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}
.workspace.has-details {
  grid-template-columns: minmax(0, 1fr) 300px;
}
.canvas-shell {
  position: relative;
  height: max(640px, calc(100vh - 320px));
  overflow: hidden;
  border: 1px solid var(--el-border-color-light);
  border-radius: 14px;
  background-color: var(--el-bg-color);
  background-image: radial-gradient(var(--el-border-color-light) 1px, transparent 1px);
  background-size: 22px 22px;
}
.graph-canvas {
  width: 100%;
  height: 100%;
}
.canvas-guide {
  position: absolute;
  top: 18px;
  left: 20px;
  font-size: 12px;
  font-weight: 600;
  pointer-events: none;
}
.canvas-guide small {
  display: block;
  margin-top: 7px;
  font-weight: 400;
  color: var(--el-text-color-secondary);
  font-size: 10px;
}
.canvas-controls {
  position: absolute;
  bottom: 40px;
  left: 16px;
  display: flex;
  gap: 6px;
}
.canvas-controls :deep(.el-button + .el-button) {
  margin-left: 0;
}
.performance {
  position: absolute;
  bottom: 14px;
  left: 20px;
  font-size: 10px;
  color: var(--el-text-color-secondary);
  pointer-events: none;
}
.hover-info {
  position: absolute;
  top: 18px;
  right: 18px;
  max-width: 65%;
  padding: 9px 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  background: var(--el-bg-color);
  font-size: 12px;
  pointer-events: none;
}
.graph-error {
  position: absolute;
  top: 80px;
  left: 20px;
  right: 20px;
}
.details {
  padding: 20px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 14px;
  background: var(--el-bg-color);
  max-height: max(640px, calc(100vh - 320px));
  overflow: auto;
  box-sizing: border-box;
}
.details-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.details h2 {
  font-size: 15px;
  margin: 0;
}
.details h3 {
  font-size: 18px;
  margin: 20px 0 12px;
}
.details h4 {
  font-size: 13px;
  margin: 24px 0 12px;
}
dl {
  font-size: 12px;
}
dt {
  color: var(--el-text-color-secondary);
  margin-top: 16px;
}
dd {
  margin: 6px 0 12px;
  overflow-wrap: anywhere;
}
.rate-card {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 16px 12px;
  margin-top: 12px;
  border-radius: 8px;
  font-size: 12px;
}
.rate-card.down {
  color: #6366f1;
  background: #6366f10d;
}
.rate-card.up {
  color: #0d9488;
  background: #0d94880d;
}
.muted {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}
.related-item {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 10px;
  margin-top: 6px;
  font-size: 11px;
  cursor: pointer;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
}
@media (max-width: 1100px) {
  .workspace.has-details {
    grid-template-columns: minmax(0, 1fr);
  }
  .details {
    max-height: 420px;
  }
  .headline-stats {
    gap: 20px;
  }
  .legend-hint {
    margin-left: 0;
  }
}
@media (max-width: 600px) {
  .validation-page {
    padding: 12px;
  }
  .canvas-shell {
    height: 600px;
  }
  .headline-stats b {
    font-size: 17px;
  }
  .toolbar-spacer {
    display: none;
  }
}
</style>
