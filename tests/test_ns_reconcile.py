"""开机对查：设备登记表与工艺链路拓扑的两处登记必须对得上。"""

from __future__ import annotations

from rubbercure.ns.reconcile import reconcile_namespace_topology
from rubbercure.ns.registry import NamespaceRegistry
from rubbercure.ns.topology import Topology


def test_default_platform_has_expected_mismatches(platform):
    report = platform.namespace_reconciliation()
    # 冷却泵登记了设备却没进链路；硫化机和控制台在链路上却没有设备登记。
    assert [item["node"] for item in report["registered_not_in_chain"]] == ["cool"]
    assert [item["node"] for item in report["chain_not_registered"]] == [
        "console",
        "press",
    ]
    assert report["ok"] is False


def test_registered_not_in_chain_lists_devices(platform):
    report = platform.namespace_reconciliation()
    (cool,) = report["registered_not_in_chain"]
    assert cool["devices"] == ["rubbercure/shop1/cool/pump"]


def test_chain_not_registered_links_are_reported(platform):
    report = platform.namespace_reconciliation()
    by_node = {item["node"]: item for item in report["chain_not_registered"]}
    assert by_node["press"]["upstream"] == ["timer"]
    assert by_node["press"]["downstream"] == ["batch"]
    assert by_node["console"]["upstream"] == ["batch", "mold", "steam", "timer", "audit"]


def test_reconciliation_passes_when_two_sides_align():
    registry = NamespaceRegistry("shop1")
    registry.register("steam", "header", "steam-header")
    registry.register("temp", "loop", "mold-temp-loop")
    topology = Topology()
    topology.add_link("steam", "temp")

    report = reconcile_namespace_topology(registry, topology)
    assert report["ok"] is True
    assert report["registered_not_in_chain"] == []
    assert report["chain_not_registered"] == []


def test_reconciliation_matches_area_not_individual_device():
    registry = NamespaceRegistry("shop1")
    registry.register("steam", "header", "steam-header")
    registry.register("steam", "valve", "steam-valve")
    topology = Topology()
    topology.add_link("steam", "temp")

    report = reconcile_namespace_topology(registry, topology)
    assert [item["node"] for item in report["registered_not_in_chain"]] == []
    assert [item["node"] for item in report["chain_not_registered"]] == ["temp"]
