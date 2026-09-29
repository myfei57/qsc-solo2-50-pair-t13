"""设备登记与工艺链路的开机前对账。

设备命名空间注册表和工艺链拓扑是分开两处登记的：注册表按
"车间／工位／设备"落名字，拓扑只记工位之间的上下游。两边各写各的就会
出现两种对不上——设备登记了却没进链路（漏节点），或者链路指向了没登记
的工位（悬空节点）。开机前用 :func:`reconcile_topology` 把两边对一遍，
把不一致的地方摊开，而不是等运行到某一步才发现名字查不到。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .registry import NamespaceRegistry
from .topology import Topology


@dataclass(frozen=True)
class TopologyMismatch:
    """一条登记与链路对不上的记录。"""

    kind: str
    name: str
    detail: str

    def as_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name, "detail": self.detail}


@dataclass(frozen=True)
class ReconcileReport:
    """对账结果：``ok`` 为真表示两处完全一致。"""

    registered_areas: tuple[str, ...]
    topology_nodes: tuple[str, ...]
    registered_not_in_topology: tuple[str, ...] = field(default=())
    topology_not_registered: tuple[str, ...] = field(default=())
    dangling_links: tuple[TopologyMismatch, ...] = field(default=())

    @property
    def ok(self) -> bool:
        return not (
            self.registered_not_in_topology
            or self.topology_not_registered
            or self.dangling_links
        )

    def problems(self) -> list[TopologyMismatch]:
        """把三类不一致摊平成可读的问题清单。"""

        problems: list[TopologyMismatch] = [
            TopologyMismatch(
                "registered_not_in_topology",
                name,
                f"工位 {name} 已在设备注册表登记，但工艺链路里没有这个节点",
            )
            for name in self.registered_not_in_topology
        ]
        problems += [
            TopologyMismatch(
                "topology_not_registered",
                name,
                f"工艺链路出现了节点 {name}，但设备注册表里没有这个工位",
            )
            for name in self.topology_not_registered
        ]
        problems += list(self.dangling_links)
        return problems

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "registered_areas": list(self.registered_areas),
            "topology_nodes": list(self.topology_nodes),
            "registered_not_in_topology": list(self.registered_not_in_topology),
            "topology_not_registered": list(self.topology_not_registered),
            "dangling_links": [item.as_dict() for item in self.dangling_links],
            "problems": [item.as_dict() for item in self.problems()],
        }


def reconcile_topology(
    registry: NamespaceRegistry, topology: Topology
) -> ReconcileReport:
    """把设备注册表的工位集合与链路节点对一遍。

    对账口径：注册表里出现的工位（``area``）与链路里的节点同名才视为一致。
    链路上任何一端没在注册表里登记，除了记为悬空节点，还要把具体那条
    上下游关系列为悬空链路，便于现场直接找到接错的位置。
    """

    registered = {entry.area for entry in registry.entries()}
    nodes = list(topology.nodes)

    only_registered = tuple(sorted(registered - set(nodes)))
    only_topology = tuple(sorted(set(nodes) - registered))

    dangling: list[TopologyMismatch] = []
    for upstream, downstream in topology.links:
        missing = [name for name in (upstream, downstream) if name not in registered]
        if missing:
            dangling.append(
                TopologyMismatch(
                    "dangling_link",
                    f"{upstream} -> {downstream}",
                    f"链路 {upstream} -> {downstream} 指向了未登记工位: {', '.join(missing)}",
                )
            )

    return ReconcileReport(
        registered_areas=tuple(sorted(registered)),
        topology_nodes=tuple(nodes),
        registered_not_in_topology=only_registered,
        topology_not_registered=only_topology,
        dangling_links=tuple(dangling),
    )
