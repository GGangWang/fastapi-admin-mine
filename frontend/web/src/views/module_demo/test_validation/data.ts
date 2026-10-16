export type DeviceKind = "office" | "service" | "host" | "controller" | "target";
export type FlowState = "active" | "idle" | "offline";
export const campuses = ["north", "east", "west"] as const;
export const DETAIL_LIMIT = 500;
export const ANIMATION_LIMIT = 200;
export interface Device {
  id: string;
  kind: DeviceKind;
  number: number;
  campusId?: string;
  groupId?: string;
  online: boolean;
}
export interface DeviceGroup {
  id: string;
  campusId: string;
  number: number;
  members: string[];
}
export interface DirectionFlow {
  rate: number;
  state: FlowState;
}
export interface Link {
  id: string;
  source: string;
  target: string;
  down: DirectionFlow;
  up: DirectionFlow;
}
export interface Topology {
  devices: Device[];
  groups: DeviceGroup[];
  links: Link[];
  deviceMap: Map<string, Device>;
  groupMap: Map<string, DeviceGroup>;
}
export interface ViewNode {
  id: string;
  kind: DeviceKind | "campus" | "group";
  campusId?: string;
  groupId?: string;
  number: number;
  count: number;
  online: number;
  x: number;
  y: number;
}
export interface ViewEdge {
  id: string;
  source: string;
  target: string;
  direction: "down" | "up";
  rate: number;
  state: FlowState;
  members: string[];
  aggregate: boolean;
}
export interface View {
  nodes: ViewNode[];
  edges: ViewEdge[];
  detailCount: number;
}
export interface Expansion {
  campuses: Set<string>;
  groups: Set<string>;
}
function hash(value: string) {
  let h = 2166136261;
  for (const char of value) h = Math.imul(h ^ char.charCodeAt(0), 16777619);
  return h >>> 0;
}
export function generateTopology(size: number): Topology {
  const devices: Device[] = [
    { id: "office-1", kind: "office", number: 1, online: true },
    { id: "office-2", kind: "office", number: 2, online: true },
    { id: "service", kind: "service", number: 1, online: true },
  ];
  const links: Link[] = [];
  const groups: DeviceGroup[] = [];
  const addLink = (source: string, target: string) =>
    links.push({
      id: `${source}:${target}`,
      source,
      target,
      down: { rate: 0, state: "idle" },
      up: { rate: 0, state: "idle" },
    });
  addLink("office-1", "service");
  addLink("office-2", "service");
  const groupCount = Math.ceil((size - 3) / 24);
  const base = Math.floor((size - 3) / groupCount);
  for (let i = 0; i < groupCount; i++) {
    const campusId = campuses[i % 3]!;
    const groupId = `group-${i + 1}`;
    const number = Math.floor(i / 3) + 1;
    const members: string[] = [];
    const count = base + (i < (size - 3) % groupCount ? 1 : 0);
    const add = (kind: DeviceKind, n: number) => {
      const id = `${groupId}-${kind}-${n}`;
      devices.push({
        id,
        kind,
        number: n,
        campusId,
        groupId,
        online: kind !== "target" || hash(id) % 41 !== 0,
      });
      members.push(id);
      return id;
    };
    const host = add("host", number);
    addLink("service", host);
    const controllers = [add("controller", 1), add("controller", 2)];
    controllers.forEach((controller) => addLink(host, controller));
    for (let j = 0; j < count - 3; j++) addLink(controllers[j % 2]!, add("target", j + 1));
    groups.push({ id: groupId, campusId, number, members });
  }
  const topology = {
    devices,
    groups,
    links,
    deviceMap: new Map(devices.map((d) => [d.id, d])),
    groupMap: new Map(groups.map((g) => [g.id, g])),
  };
  updateFlows(topology, 0);
  return topology;
}
export function updateFlows(topology: Topology, tick: number) {
  for (const link of topology.links) {
    const online =
      topology.deviceMap.get(link.source)!.online && topology.deviceMap.get(link.target)!.online;
    for (const direction of ["down", "up"] as const) {
      const seed = hash(`${link.id}:${direction}:${tick}`);
      const state: FlowState = !online ? "offline" : seed % 9 === 0 ? "idle" : "active";
      link[direction] = {
        state,
        rate:
          state === "active"
            ? Math.round((direction === "up" ? 80 : 5) + (seed % (direction === "up" ? 9000 : 800)))
            : 0,
      };
    }
  }
}
export function initialExpansion(topology: Topology): Expansion {
  return {
    campuses: new Set(topology.devices.length <= 100 ? campuses : []),
    groups: new Set<string>(),
  };
}
export function expandGroup(topology: Topology, expansion: Expansion, id: string, force = false) {
  const group = topology.groupMap.get(id);
  if (!group) return false;
  const count = [...expansion.groups].reduce(
    (sum, key) => sum + (topology.groupMap.get(key)?.members.length ?? 0),
    3
  );
  if (!expansion.groups.has(id) && count + group.members.length > DETAIL_LIMIT) {
    if (!force) return false;
    expansion.groups.clear();
  }
  expansion.campuses.add(group.campusId);
  expansion.groups.add(id);
  return true;
}
export function projectTopology(topology: Topology, expansion: Expansion, campus = "all"): View {
  const selectedCampuses = campuses.filter((id) => campus === "all" || id === campus);
  const devices = topology.devices.filter(
    (d) => !d.campusId || selectedCampuses.includes(d.campusId as (typeof campuses)[number])
  );
  const nodes: ViewNode[] = [];
  const addNode = (
    id: string,
    kind: ViewNode["kind"],
    members: Device[],
    x: number,
    y: number,
    campusId?: string,
    groupId?: string,
    number = 1
  ) =>
    nodes.push({
      id,
      kind,
      count: members.length,
      online: members.filter((d) => d.online).length,
      x,
      y,
      campusId,
      groupId,
      number,
    });
  let y = 0;
  for (const campusId of selectedCampuses) {
    const members = devices.filter((d) => d.campusId === campusId);
    const top = y;
    if (!expansion.campuses.has(campusId)) {
      addNode(`campus-${campusId}`, "campus", members, 740, y + 70, campusId);
      y += 220;
    } else {
      const groups = topology.groups.filter((g) => g.campusId === campusId);
      for (const group of groups) {
        const groupMembers = group.members.map((id) => topology.deviceMap.get(id)!);
        if (!expansion.groups.has(group.id)) {
          addNode(group.id, "group", groupMembers, 1040, y + 40, campusId, group.id, group.number);
          y += 120;
        } else {
          const targets = groupMembers.filter((d) => d.kind === "target");
          const height = Math.max(180, Math.ceil(targets.length / 3) * 86);
          for (const d of groupMembers) {
            const index = targets.indexOf(d);
            const x =
              d.kind === "host" ? 1040 : d.kind === "controller" ? 1320 : 1590 + (index % 3) * 240;
            const nodeY =
              d.kind === "host"
                ? y + height / 2
                : d.kind === "controller"
                  ? y + height * (d.number === 1 ? 0.25 : 0.75)
                  : y + Math.floor(index / 3) * 86 + 40;
            addNode(d.id, d.kind, [d], x, nodeY, campusId, group.id, d.number);
          }
          y += height + 70;
        }
      }
      addNode(`campus-${campusId}`, "campus", members, 740, (top + y) / 2, campusId);
      y += 80;
    }
  }
  addNode("service", "service", [topology.deviceMap.get("service")!], 390, y / 2);
  for (const id of ["office-1", "office-2"]) {
    const device = topology.deviceMap.get(id)!;
    addNode(
      id,
      "office",
      [device],
      60,
      y / 2 + (device.number === 1 ? -80 : 80),
      undefined,
      undefined,
      device.number
    );
  }
  const endpoint = (d: Device) =>
    !d.campusId
      ? d.id
      : !expansion.campuses.has(d.campusId)
        ? `campus-${d.campusId}`
        : !expansion.groups.has(d.groupId!)
          ? d.groupId!
          : d.id;
  const edges = new Map<string, ViewEdge>();
  const ids = new Set(devices.map((d) => d.id));
  function aggregate(
    source: string,
    target: string,
    direction: ViewEdge["direction"],
    flow: DirectionFlow,
    memberId: string,
    aggregateEdge: boolean
  ) {
    const id = `${source}>${target}:${direction}`;
    let edge = edges.get(id);
    if (!edge) {
      edge = {
        id,
        source,
        target,
        direction,
        rate: 0,
        state: "offline",
        members: [],
        aggregate: aggregateEdge,
      };
      edges.set(id, edge);
    }
    edge.rate += flow.rate;
    edge.members.push(memberId);
    if (flow.state === "active") edge.state = "active";
    else if (flow.state === "idle" && edge.state !== "active") edge.state = "idle";
  }
  for (const link of topology.links) {
    if (!ids.has(link.source) || !ids.has(link.target)) continue;
    const source = endpoint(topology.deviceMap.get(link.source)!);
    const target = endpoint(topology.deviceMap.get(link.target)!);
    if (source === target) continue;
    const aggregated = source !== link.source || target !== link.target;
    aggregate(source, target, "down", link.down, link.id, aggregated);
    aggregate(target, source, "up", link.up, link.id, aggregated);
  }
  // 展开的园区节点作为导航入口；真实跨园区链路仍按设备组聚合，不虚构额外流量。
  return {
    nodes,
    edges: [...edges.values()],
    detailCount: nodes.filter((n) => n.kind !== "campus" && n.kind !== "group").length,
  };
}
export function animationIds(edges: ViewEdge[], selectedId: string, enabled: boolean) {
  if (!enabled) return new Set<string>();
  return new Set(
    edges
      .filter((e) => e.state === "active")
      .sort(
        (a, b) =>
          Number(b.id === selectedId || b.source === selectedId || b.target === selectedId) -
            Number(a.id === selectedId || a.source === selectedId || a.target === selectedId) ||
          b.rate - a.rate ||
          a.id.localeCompare(b.id)
      )
      .slice(0, ANIMATION_LIMIT)
      .map((e) => e.id)
  );
}
export function formatRate(rate: number) {
  return rate >= 1000 ? `${(rate / 1000).toFixed(1)} MB/s` : `${rate.toFixed(0)} kB/s`;
}
