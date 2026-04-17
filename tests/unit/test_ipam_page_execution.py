"""Execution tests for src/ui/pages/ipam.py."""

from __future__ import annotations

import asyncio
import inspect
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from src.models.ipam import (
    IpamAllocationGroupResponse,
    IpamDeviceClaimResponse,
    IpamNetworkDetailResponse,
    IpamNetworkListResponse,
    IpamNetworkSummaryResponse,
    IpamPageStatsResponse,
)
from src.models.types import (
    DeviceStatus,
    DeviceType,
    IpamAddressFamily,
    IpamCellStatus,
    IpamRenderMode,
)
from src.ui.services.ipam_search import IpamSearchTargets
from tests.unit.nicegui_fakes import FakeUI, install_fake_ui


async def _invoke(handler: Callable[..., object]) -> object:
    result = handler()
    if inspect.isawaitable(result):
        return await result
    return result


@contextmanager
def _noop_shell() -> Iterator[None]:
    yield


def _summary_payload(network_id: uuid.UUID) -> IpamNetworkListResponse:
    return IpamNetworkListResponse(
        summary=IpamPageStatsResponse(
            total_networks=1,
            visualizable_networks=1,
            total_assigned_ips=1,
            total_conflicts=0,
            most_utilized_network=None,
        ),
        items=[
            IpamNetworkSummaryResponse(
                network_id=network_id,
                name="Management",
                vlan_id=10,
                cidr="10.0.10.0/24",
                gateway="10.0.10.1",
                color="#3b82f6",
                address_family=IpamAddressFamily.ipv4,
                render_mode=IpamRenderMode.grid,
                usable_ip_count=254,
                used_ip_count=1,
                free_ip_count=253,
                conflict_ip_count=0,
                device_claim_count=1,
                utilization_pct=0.39,
                block_count=None,
                unsupported_reason=None,
            )
        ],
    )


def _detail_payload(network_id: uuid.UUID, device_id: uuid.UUID) -> IpamNetworkDetailResponse:
    summary = _summary_payload(network_id).items[0]
    return IpamNetworkDetailResponse(
        network=summary,
        cells=[],
        blocks=[],
        allocations=[
            IpamAllocationGroupResponse(
                address="10.0.10.42",
                block_cidr="10.0.10.0/24",
                status=IpamCellStatus.used,
                device_claims=[
                    IpamDeviceClaimResponse(
                        device_id=device_id,
                        device_name="nas-01",
                        device_type=DeviceType.NAS,
                        device_status=DeviceStatus.Active,
                        mac="aa:bb:cc:dd:ee:ff",
                        ip_address="10.0.10.42",
                    )
                ],
            )
        ],
    )


class TestIpamPage:
    def test_page_load_expand_cache_search_and_navigation(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.ipam as ipam_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, ipam_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(ipam_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(ipam_module, "redirect_if_unauthenticated", lambda **kwargs: False)

        network_id = uuid.uuid4()
        device_id = uuid.uuid4()
        summary_payload = _summary_payload(network_id)
        detail_payload = _detail_payload(network_id, device_id)

        summary_calls: list[str] = []
        detail_calls: list[str] = []
        search_calls: list[str] = []
        open_device_cb: dict[str, Callable[[str], None]] = {}

        async def fake_load_summary(token: str) -> IpamNetworkListResponse:
            summary_calls.append(token)
            return summary_payload

        async def fake_load_detail(token: str, requested_network_id: str) -> IpamNetworkDetailResponse:
            detail_calls.append(f"{token}:{requested_network_id}")
            return detail_payload

        def fake_resolve_visible_matches(
            query: str,
            details_by_network: dict[str, IpamNetworkDetailResponse],
        ) -> dict[str, IpamSearchTargets]:
            search_calls.append(query)
            if not query.strip():
                return {}
            if not details_by_network:
                return {}
            return {
                str(network_id): IpamSearchTargets(
                    cell_ids=(f"ipam-cell-{network_id}-10-0-10-42",),
                    scroll_target_id=f"ipam-cell-{network_id}-10-0-10-42",
                )
            }

        def fake_render_stats_row(_summary: IpamPageStatsResponse) -> None:
            return None

        def fake_render_grid(
            _detail: IpamNetworkDetailResponse,
            _targets: IpamSearchTargets,
            on_open_device: Callable[[str], None],
            _network_key: str,
        ) -> None:
            open_device_cb["fn"] = on_open_device

        monkeypatch.setattr(ipam_module, "load_ipam_summary", fake_load_summary)
        monkeypatch.setattr(ipam_module, "load_ipam_detail", fake_load_detail)
        monkeypatch.setattr(ipam_module, "resolve_visible_matches", fake_resolve_visible_matches)
        monkeypatch.setattr(ipam_module, "render_ipam_stats_row", fake_render_stats_row)
        monkeypatch.setattr(ipam_module, "render_ipam_grid", fake_render_grid)
        monkeypatch.setattr(ipam_module, "render_ipam_block_summary", lambda *args, **kwargs: None)

        async def exercise() -> None:
            await ipam_module.ipam_page()

            assert summary_calls == ["token"]
            assert detail_calls == []

            expansion = fake_ui.created["expansion"][0]
            await _invoke(lambda: expansion.handlers["value_change"](SimpleNamespace(value=True)))
            assert len(detail_calls) == 1

            await _invoke(lambda: expansion.handlers["value_change"](SimpleNamespace(value=True)))
            assert len(detail_calls) == 1

            open_device_cb["fn"](str(device_id))
            assert (f"/topology?device_id={device_id}", False) in fake_ui.navigate.to_calls

            search_input = fake_ui.created["input"][0]
            await _invoke(lambda: search_input.handlers["value_change"](SimpleNamespace(value="nas")))
            assert search_calls[-1] == "nas"
            assert len(detail_calls) == 1
            assert len(summary_calls) == 1

        asyncio.run(exercise())

    def test_reverse_detail_load_order_scrolls_to_first_match_in_summary_order(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.pages.ipam as ipam_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, ipam_module, fake_ui, {"access_token": "token"})
        monkeypatch.setattr(ipam_module, "app_shell", lambda *args, **kwargs: _noop_shell())
        monkeypatch.setattr(ipam_module, "redirect_if_unauthenticated", lambda **kwargs: False)

        first_network_id = uuid.uuid4()
        second_network_id = uuid.uuid4()
        first_device_id = uuid.uuid4()
        second_device_id = uuid.uuid4()

        summary_payload = IpamNetworkListResponse(
            summary=IpamPageStatsResponse(
                total_networks=2,
                visualizable_networks=2,
                total_assigned_ips=2,
                total_conflicts=0,
                most_utilized_network=None,
            ),
            items=[
                IpamNetworkSummaryResponse(
                    network_id=first_network_id,
                    name="First",
                    vlan_id=10,
                    cidr="10.0.10.0/24",
                    gateway="10.0.10.1",
                    color="#3b82f6",
                    address_family=IpamAddressFamily.ipv4,
                    render_mode=IpamRenderMode.grid,
                    usable_ip_count=254,
                    used_ip_count=1,
                    free_ip_count=253,
                    conflict_ip_count=0,
                    device_claim_count=1,
                    utilization_pct=0.39,
                    block_count=None,
                    unsupported_reason=None,
                ),
                IpamNetworkSummaryResponse(
                    network_id=second_network_id,
                    name="Second",
                    vlan_id=20,
                    cidr="10.0.20.0/24",
                    gateway="10.0.20.1",
                    color="#22c55e",
                    address_family=IpamAddressFamily.ipv4,
                    render_mode=IpamRenderMode.grid,
                    usable_ip_count=254,
                    used_ip_count=1,
                    free_ip_count=253,
                    conflict_ip_count=0,
                    device_claim_count=1,
                    utilization_pct=0.39,
                    block_count=None,
                    unsupported_reason=None,
                ),
            ],
        )

        first_detail = IpamNetworkDetailResponse(
            network=summary_payload.items[0],
            cells=[],
            blocks=[],
            allocations=[
                IpamAllocationGroupResponse(
                    address="10.0.10.42",
                    block_cidr="10.0.10.0/24",
                    status=IpamCellStatus.used,
                    device_claims=[
                        IpamDeviceClaimResponse(
                            device_id=first_device_id,
                            device_name="match-device-a",
                            device_type=DeviceType.NAS,
                            device_status=DeviceStatus.Active,
                            mac=None,
                            ip_address="10.0.10.42",
                        )
                    ],
                )
            ],
        )
        second_detail = IpamNetworkDetailResponse(
            network=summary_payload.items[1],
            cells=[],
            blocks=[],
            allocations=[
                IpamAllocationGroupResponse(
                    address="10.0.20.42",
                    block_cidr="10.0.20.0/24",
                    status=IpamCellStatus.used,
                    device_claims=[
                        IpamDeviceClaimResponse(
                            device_id=second_device_id,
                            device_name="match-device-b",
                            device_type=DeviceType.Server,
                            device_status=DeviceStatus.Active,
                            mac=None,
                            ip_address="10.0.20.42",
                        )
                    ],
                )
            ],
        )

        detail_calls: list[str] = []

        async def fake_load_summary(_token: str) -> IpamNetworkListResponse:
            return summary_payload

        async def fake_load_detail(_token: str, requested_network_id: str) -> IpamNetworkDetailResponse:
            detail_calls.append(requested_network_id)
            if requested_network_id == str(first_network_id):
                return first_detail
            if requested_network_id == str(second_network_id):
                return second_detail
            raise AssertionError(f"Unexpected network id: {requested_network_id}")

        monkeypatch.setattr(ipam_module, "load_ipam_summary", fake_load_summary)
        monkeypatch.setattr(ipam_module, "load_ipam_detail", fake_load_detail)
        monkeypatch.setattr(ipam_module, "render_ipam_stats_row", lambda _summary: None)
        monkeypatch.setattr(ipam_module, "render_ipam_grid", lambda *args, **kwargs: None)
        monkeypatch.setattr(ipam_module, "render_ipam_block_summary", lambda *args, **kwargs: None)

        async def exercise() -> None:
            await ipam_module.ipam_page()

            first_expansion = fake_ui.created["expansion"][0]
            second_expansion = fake_ui.created["expansion"][1]

            await _invoke(lambda: second_expansion.handlers["value_change"](SimpleNamespace(value=True)))
            await _invoke(lambda: first_expansion.handlers["value_change"](SimpleNamespace(value=True)))

            assert detail_calls == [str(second_network_id), str(first_network_id)]

            search_input = fake_ui.created["input"][0]
            await _invoke(lambda: search_input.handlers["value_change"](SimpleNamespace(value="match-device")))

            assert len(fake_ui.run_javascript_calls) == 1
            assert str(first_network_id) in fake_ui.run_javascript_calls[0]
            assert str(second_network_id) not in fake_ui.run_javascript_calls[0]

        asyncio.run(exercise())
