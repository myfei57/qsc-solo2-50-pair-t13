"""设备登记与工艺链路的开机对查。

设备命名空间（注册表）和工艺链路（拓扑）是两处分别登记的：注册表按
"车间／工位／设备" 记真实设备，拓扑只记节点名和上下游约束。两边没有任何
强制同步，漏登或错名都不会在装配阶段暴露。开机前调用本模块把两边对一遍，
列出"登记了但没进链路"和"链路指向但没登记"两类差异。
"""

from __future__ import annotations

from .registry import NamespaceRegistry
from .topology import Topology


def reconcile_namespace_topology(
    registry: NamespaceRegistry, topology: Topology
) -> dict:
    """对查设备注册表与链路拓扑，返回差异报告。

    拓扑节点与注册表工位（``area``）按名字比对：设备侧同一工位下可能挂多台
    设备，报告里把它们的完整路径列出来，方便现场核对具体是哪一台。
    """

    registered = {entry["area"]: entry for entry in registry.describe()}
    devices_by_area: dict[str, list[str]] = {}
    for entry in registry.describe():
        devices_by_area.setdefault(entry["area"], []).append(entry["path"])

    registered_only = sorted(set(registered) - set(topology.nodes))
    topology_only = sorted(set(topology.nodes) - set(registered))

    return {
        "registered_areas": sorted(registered),
        "topology_nodes": list(topology.nodes),
        # 登记了设备却没进链路：该工位不受任何上下游顺序约束。
        "registered_not_in_chain": [
            {"node": area, "devices": sorted(devices_by_area[area])}
            for area in registered_only
        ],
        # 链路指向了不存在的设备登记：顺序约束落在空节点上。
        "chain_not_registered": [
            {
                "node": node,
                "upstream": topology.upstream_of(node),
                "downstream": topology.downstream_of(node),
            }
            for node in topology_only
        ],
        "ok": not registered_only and not topology_only,
    }
