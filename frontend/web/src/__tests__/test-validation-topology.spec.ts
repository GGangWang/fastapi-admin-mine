// @vitest-environment node
import { describe, expect, it } from "vitest";
import {
  ANIMATION_LIMIT,
  DETAIL_LIMIT,
  animationIds,
  expandGroup,
  generateTopology,
  initialExpansion,
  projectTopology,
  updateFlows,
} from "@/views/module_demo/test_validation/data";

describe("G6 topology projection and simulated traffic", () => {
  for (const size of [100, 1000, 5000]) {
    it(`creates ${size} deterministic devices and valid bidirectional graph`, () => {
      const topology = generateTopology(size);
      expect(topology.devices).toHaveLength(size);
      expect(new Set(topology.devices.map((d) => d.id)).size).toBe(size);
      expect(topology.devices).toEqual(generateTopology(size).devices);
      expect(
        topology.links.every(
          (link) => topology.deviceMap.has(link.source) && topology.deviceMap.has(link.target)
        )
      ).toBe(true);
      const expansion = initialExpansion(topology);
      for (const campus of ["all", "north", "east", "west"]) {
        const view = projectTopology(topology, expansion, campus);
        const ids = new Set(view.nodes.map((node) => node.id));
        expect(ids.has("service") && ids.has("office-1") && ids.has("office-2")).toBe(true);
        expect(
          view.nodes.every((node) => campus === "all" || !node.campusId || node.campusId === campus)
        ).toBe(true);
        expect(
          view.edges.every(
            (edge) => ids.has(edge.source) && ids.has(edge.target) && edge.source !== edge.target
          )
        ).toBe(true);
        expect(new Set(view.edges.map((edge) => edge.id)).size).toBe(view.edges.length);
        for (const edge of view.edges) {
          expect(
            view.edges.some(
              (other) =>
                other.source === edge.target &&
                other.target === edge.source &&
                other.direction !== edge.direction
            )
          ).toBe(true);
          const sum = edge.members.reduce(
            (rate, id) =>
              rate + topology.links.find((link) => link.id === id)![edge.direction].rate,
            0
          );
          expect(edge.rate).toBe(sum);
        }
      }
    });
  }
  it("aggregates member counts, online counts, and campus uplink rates", () => {
    const topology = generateTopology(5000);
    const view = projectTopology(topology, initialExpansion(topology));
    expect(view.nodes).toHaveLength(6);
    const node = view.nodes.find((n) => n.id === "campus-north")!;
    const devices = topology.devices.filter((d) => d.campusId === "north");
    expect(node.count).toBe(devices.length);
    expect(node.online).toBe(devices.filter((d) => d.online).length);
    const edge = view.edges.find((e) => e.source === node.id && e.target === "service")!;
    expect(edge.rate).toBe(
      topology.links
        .filter(
          (link) =>
            link.source === "service" && topology.deviceMap.get(link.target)!.campusId === "north"
        )
        .reduce((sum, link) => sum + link.up.rate, 0)
    );
  });
  it("enforces detail limit and makes search-forced expansion possible", () => {
    const topology = generateTopology(5000);
    const expansion = initialExpansion(topology);
    let blocked = false;
    for (const group of topology.groups) {
      if (!expandGroup(topology, expansion, group.id)) {
        blocked = true;
        break;
      }
    }
    expect(blocked).toBe(true);
    expect(projectTopology(topology, expansion).detailCount).toBeLessThanOrEqual(DETAIL_LIMIT);
    const last = topology.groups.at(-1)!;
    expect(expandGroup(topology, expansion, last.id, true)).toBe(true);
    expect(projectTopology(topology, expansion).nodes.some((n) => n.id === last.members[0])).toBe(
      true
    );
    expect(projectTopology(topology, expansion).detailCount).toBeLessThanOrEqual(DETAIL_LIMIT);
  });
  it("updates directions independently and keeps offline links at zero", () => {
    const topology = generateTopology(1000);
    const previous = topology.links.map((link) => link.up.rate);
    updateFlows(topology, 10);
    expect(topology.links.map((link) => link.up.rate)).not.toEqual(previous);
    const offline = topology.links.filter(
      (link) =>
        !topology.deviceMap.get(link.source)!.online || !topology.deviceMap.get(link.target)!.online
    );
    expect(offline.length).toBeGreaterThan(0);
    for (const link of offline)
      for (const direction of ["up", "down"] as const) {
        expect(link[direction]).toEqual({ rate: 0, state: "offline" });
      }
    expect(topology.links.some((link) => link.down.state !== link.up.state)).toBe(true);
  });
  it("caps animations and prioritizes selected links ahead of throughput", () => {
    const topology = generateTopology(1000);
    const expansion = initialExpansion(topology);
    for (const group of topology.groups.slice(0, 19)) expandGroup(topology, expansion, group.id);
    const view = projectTopology(topology, expansion);
    const selected = view.edges.filter((e) => e.state === "active").at(-1)!;
    const ids = animationIds(view.edges, selected.id, true);
    expect(ids.size).toBe(ANIMATION_LIMIT);
    expect(ids.has(selected.id)).toBe(true);
    expect(animationIds(view.edges, selected.id, false).size).toBe(0);
    expect(
      [...ids].every((id) => view.edges.find((edge) => edge.id === id)!.state === "active")
    ).toBe(true);
  });
});
