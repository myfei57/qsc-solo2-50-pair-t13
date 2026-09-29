"""设备登记与工艺链路的开机前对账。"""

from __future__ import annotations

from rubbercure.ns.registry import NamespaceRegistry
from rubbercure.ns.reconcile import reconcile_topology
from rubbercure.ns.topology import Topology


def _registry(*areas: str) -> NamespaceRegistry:
    registry = NamespaceRegistry("shop1")
    for area in areas:
        registry.register(area, f"{area}-device", f"{area}-kind")
    return registry


def test_default_platform_has_known_mismatches(platform):
    """交付基线里两处登记的历史不一致必须被对账抓出来。"""

    report = platform.preflight_topology()
    assert report["ok"] is False
    # cool 冷却设备登记了却没进工艺链。
    assert report["registered_not_in_topology"] == ["cool"]
    # press、console 在链路里却没有命名空间登记。
    assert report["topology_not_registered"] == ["console", "press"]
    dangling = {item["name"] for item in report["dangling_links"]}
    assert "timer -> press" in dangling
    assert "press -> batch" in dangling
    assert "audit -> console" in dangling
    # 每条悬空链路都要指明是哪一端没登记。
    assert all(item["kind"] == "dangling_link" for item in report["dangling_links"])


def test_reconcile_passes_when_registry_matches_topology():
    registry = _registry("a", "b", "c")
    topology = Topology()
    topology.add_link("a", "b")
    topology.add_link("b", "c")

    report = reconcile_topology(registry, topology)
    assert report.ok is True
    assert report.problems() == []
    assert report.as_dict()["problems"] == []


def test_reconcile_flags_registered_device_missing_from_chain():
    registry = _registry("a", "b", "orphan")
    topology = Topology()
    topology.add_link("a", "b")

    report = reconcile_topology(registry, topology)
    assert report.ok is False
    assert report.registered_not_in_topology == ("orphan",)
    assert report.topology_not_registered == ()
    assert report.dangling_links == ()


def test_reconcile_flags_chain_pointing_at_unregistered_device():
    registry = _registry("a")
    topology = Topology()
    topology.add_link("a", "ghost")

    report = reconcile_topology(registry, topology)
    assert report.ok is False
    assert report.registered_not_in_topology == ()
    assert report.topology_not_registered == ("ghost",)
    assert len(report.dangling_links) == 1
    mismatch = report.dangling_links[0]
    assert mismatch.kind == "dangling_link"
    assert mismatch.name == "a -> ghost"
    assert "ghost" in mismatch.detail
