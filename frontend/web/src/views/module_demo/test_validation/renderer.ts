import { Graph, Quadratic, ExtensionCategory, register } from "@antv/g6";
import type { GraphData, NodeData, EdgeData } from "@antv/g6";
import { animationIds, formatRate } from "./data";
import type { View, ViewNode, ViewEdge } from "./data";

const flowAnimations = new WeakMap<object, { pause(): void; play(): void; cancel(): void }>();
class TrafficEdge extends Quadratic {
  override render(...args: Parameters<Quadratic["render"]>) {
    super.render(...args);
    const flowing = Boolean((args[0] as { flowing?: boolean } | undefined)?.flowing);
    let animation = flowAnimations.get(this);
    if (flowing && !animation) {
      const created = this.getShape("key").animate(
        [{ lineDashOffset: 0 }, { lineDashOffset: -20 }],
        { duration: 900, iterations: Infinity }
      );
      if (created) {
        animation = created;
        flowAnimations.set(this, created);
      }
    }
    if (flowing) animation?.play();
    else animation?.pause();
  }
  override destroy() {
    flowAnimations.get(this)?.cancel();
    flowAnimations.delete(this);
    super.destroy();
  }
}
register(ExtensionCategory.EDGE, "validation-traffic", TrafficEdge);
export const colors = {
  office: "#64748b",
  service: "#6366f1",
  host: "#0284c7",
  controller: "#d97706",
  target: "#059669",
  campus: "#6366f1",
  group: "#0284c7",
};
const glyphs = {
  office: "▣",
  service: "◈",
  host: "▣",
  controller: "⚙",
  target: "▤",
  campus: "▦",
  group: "⊞",
};
export interface RendererOptions {
  label(node: ViewNode): string;
  text(key: string): string;
  select(id: string): void;
  toggle(id: string): void;
  hover(id: string): void;
  error(error: unknown): void;
  transform(active: boolean): void;
}
export class TopologyRenderer {
  readonly graph: Graph;
  private view: View = { nodes: [], edges: [], detailCount: 0 };
  private selected = "";
  private animations = true;
  private running = true;
  private moving = false;
  private transformTimer?: ReturnType<typeof setTimeout>;
  private selectionTimer?: ReturnType<typeof setTimeout>;
  private queue: Promise<void> = Promise.resolve();
  private disposed = false;
  private rendered = false;
  private refreshQueued = false;
  private textColor = "#334155";
  private fill = "#ffffff";
  private border = "#e2e8f0";
  private dark = false;
  constructor(
    container: HTMLElement,
    private options: RendererOptions
  ) {
    this.graph = new Graph({
      container,
      width: container.clientWidth,
      height: container.clientHeight,
      animation: false,
      padding: 36,
      zoomRange: [0.03, 2],
      node: { type: "rect" },
      edge: { type: "validation-traffic" },
      combo: {
        type: "rect",
        style: {
          radius: 18,
          padding: 35,
          labelPlacement: "top-left",
          lineDash: [6, 5],
          lineWidth: 1,
        },
      },
      behaviors: [
        "drag-canvas",
        "zoom-canvas",
        { type: "optimize-viewport-transform", enable: () => this.view.nodes.length > 100 },
      ],
    });
    this.graph.on("node:click", (event) => {
      const id =
        "target" in event && event.target && "id" in event.target ? String(event.target.id) : "";
      clearTimeout(this.selectionTimer);
      this.selectionTimer = setTimeout(() => options.select(id), 220);
    });
    this.graph.on("node:dblclick", (event) => {
      clearTimeout(this.selectionTimer);
      const id =
        "target" in event && event.target && "id" in event.target ? String(event.target.id) : "";
      if (
        this.view.nodes.some(
          (node) => node.id === id && (node.kind === "campus" || node.kind === "group")
        )
      )
        options.toggle(id);
    });
    this.graph.on("edge:click", (event) =>
      options.select(
        "target" in event && event.target && "id" in event.target ? String(event.target.id) : ""
      )
    );
    this.graph.on("canvas:click", () => {
      clearTimeout(this.selectionTimer);
      options.select("");
    });
    this.graph.on("canvas:dragstart", () => options.transform(true));
    this.graph.on("canvas:dragend", () => options.transform(false));
    this.graph.on("node:pointerenter", (event) =>
      options.hover(
        "target" in event && event.target && "id" in event.target ? String(event.target.id) : ""
      )
    );
    this.graph.on("edge:pointerenter", (event) =>
      options.hover(
        "target" in event && event.target && "id" in event.target ? String(event.target.id) : ""
      )
    );
    this.graph.on("node:pointerleave", () => options.hover(""));
    this.graph.on("edge:pointerleave", () => options.hover(""));
    this.graph.on("beforetransform", () => {
      if (!this.moving) {
        this.moving = true;

        this.refresh(this.view, this.selected);
      }
      clearTimeout(this.transformTimer);
    });
    this.graph.on("aftertransform", () => {
      clearTimeout(this.transformTimer);
      this.transformTimer = setTimeout(() => {
        this.moving = false;

        this.refresh(this.view, this.selected);
      }, 160);
    });
  }
  private enqueue(task: () => Promise<void>) {
    this.queue = this.queue
      .then(async () => {
        if (!this.disposed) await task();
      })
      .catch((error) => {
        this.options.error(error);
      });
    return this.queue;
  }
  private palette() {
    const style = getComputedStyle(document.documentElement);
    this.textColor = style.getPropertyValue("--el-text-color-primary").trim() || "#334155";
    this.fill = style.getPropertyValue("--el-bg-color").trim() || "#ffffff";
    this.border = style.getPropertyValue("--el-border-color").trim() || "#e2e8f0";
    this.dark = document.documentElement.classList.contains("dark");
  }
  private nodeData(node: ViewNode): NodeData {
    const related = this.view.edges.some(
      (edge) =>
        (edge.source === this.selected && edge.target === node.id) ||
        (edge.target === this.selected && edge.source === node.id) ||
        (edge.id === this.selected && (edge.source === node.id || edge.target === node.id))
    );
    const aggregate = node.kind === "campus" || node.kind === "group";
    const color = colors[node.kind];
    const onlineText = aggregate
      ? `${node.online}/${node.count} ${this.options.text("online")}`
      : this.options.text(node.online ? "online" : "offline");
    return {
      id: node.id,
      combo: node.campusId ? `boundary-${node.campusId}` : undefined,
      data: { kind: node.kind },
      style: {
        x: node.x,
        y: node.y,
        size: aggregate ? [220, 92] : [200, 70],
        radius: 10,
        fill: this.fill,
        stroke: node.id === this.selected ? color : this.border,
        lineWidth: node.id === this.selected ? 3 : 1,
        shadowColor: this.dark ? "transparent" : "#0f172a0d",
        shadowBlur: 10,
        opacity: this.selected && node.id !== this.selected && !related ? 0.35 : 1,
        iconText: glyphs[node.kind],
        iconFill: color,
        iconFontSize: 22,
        iconX: -76,
        iconY: -5,
        label: !this.rendered || this.graph.getZoom() >= 0.28 || aggregate,
        labelText: `${this.options.label(node)}\n${onlineText}`,
        labelFill: this.textColor,
        labelFontSize: 12,
        labelLineHeight: 22,
        labelMaxLines: 2,
        labelPlacement: "center",
        labelOffsetX: 17,
        labelWordWrap: true,
        labelMaxWidth: 155,
        badge: !aggregate,
        badges: [
          {
            text: "",
            placement: "right-top",
            fill: node.online ? "#10b981" : "#94a3b8",
            fontSize: 1,
            padding: 3,
          },
        ],
      },
    };
  }
  private edgeData(edge: ViewEdge, animated: Set<string>): EdgeData {
    const relevant =
      !this.selected ||
      edge.id === this.selected ||
      edge.source === this.selected ||
      edge.target === this.selected;
    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      style: {
        curveOffset: 20,
        endArrow: true,
        endArrowSize: 6,
        stroke:
          edge.state === "offline" ? "#94a3b8" : edge.direction === "down" ? "#6366f1" : "#0d9488",
        lineWidth: relevant && this.selected ? 2.5 : 1.4,
        opacity: relevant ? (edge.state === "offline" ? 0.35 : 0.75) : 0.12,
        lineDash: edge.state === "active" ? [8, 12] : [3, 6],
        flowing: animated.has(edge.id),
        label: !this.moving && (edge.aggregate || edge.id === this.selected),
        labelText: `${edge.direction === "down" ? "↓" : "↑"} ${formatRate(edge.rate)}`,
        labelFill: this.textColor,
        labelFontSize: 10,
        labelBackground: true,
        labelBackgroundFill: this.fill,
        labelOffsetY: -7,
      },
    };
  }
  private data(): GraphData {
    const animated = animationIds(
      this.view.edges,
      this.selected,
      this.animations && this.running && !this.moving
    );
    const campusIds = [
      ...new Set(this.view.nodes.map((n) => n.campusId).filter((id): id is string => Boolean(id))),
    ];
    return {
      nodes: this.view.nodes.map((node) => this.nodeData(node)),
      edges: this.view.edges.map((edge) => this.edgeData(edge, animated)),
      combos: campusIds.map((id) => ({
        id: `boundary-${id}`,
        style: {
          labelText: this.options.text(id),
          labelFill: this.textColor,
          fill: this.dark ? "#818cf808" : "#6366f106",
          stroke: this.border,
        },
      })),
    };
  }
  rebuild(view: View, fit = true, selected = "") {
    this.selected = selected;
    this.view = view;
    return this.enqueue(async () => {
      this.palette();
      this.graph.setData(this.data());
      await this.graph.render();
      this.rendered = true;
      if (fit) await this.graph.fitView({ when: "always" }, false);
    });
  }
  refresh(view: View, selected: string) {
    this.view = view;
    this.selected = selected;
    if (this.refreshQueued) return this.queue;
    this.refreshQueued = true;
    return this.enqueue(async () => {
      this.refreshQueued = false;
      this.palette();
      const data = this.data();
      this.graph.updateEdgeData(data.edges!);
      this.graph.updateNodeData(data.nodes!);
      this.graph.updateComboData(data.combos!);
      await this.graph.draw();
    });
  }
  setPlayback(running: boolean, animations: boolean) {
    this.running = running;
    this.animations = animations;
    if (!running) clearTimeout(this.selectionTimer);
    if (!this.rendered) return Promise.resolve();
    return this.refresh(this.view, this.selected);
  }
  fit() {
    return this.enqueue(() => this.graph.fitView({ when: "always" }, false));
  }
  focus(id: string) {
    return this.enqueue(async () => {
      await this.graph.zoomTo(0.85, false);
      await this.graph.focusElement(id, false);
    });
  }
  zoom(factor: number) {
    return this.enqueue(() =>
      this.graph.zoomTo(Math.min(2, Math.max(0.03, this.graph.getZoom() * factor)), false)
    );
  }
  resize(width: number, height: number) {
    if (!this.disposed) this.graph.setSize(width, height);
  }
  destroy() {
    this.disposed = true;
    clearTimeout(this.transformTimer);
    clearTimeout(this.selectionTimer);
    this.graph.destroy();
  }
}
