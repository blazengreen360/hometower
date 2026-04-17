"""Regression tests for HT-070 workspace timestamp rendering on /workspaces."""
from __future__ import annotations

import asyncio
import re
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
import pytest

from src.ui.utils import formatting as formatting_module
from tests.unit.nicegui_fakes import AsyncClientStub, FakeUI, install_fake_ui


@contextmanager
def _noop_shell() -> Iterator[None]:
    yield


def _extract_retry_contract(script: str) -> tuple[int, int]:
    attempts_match = re.search(r"attempts\s*>=\s*(\d+)", script)
    interval_match = re.search(r"setInterval\(function \(\) \{.*?\},\s*(\d+)\);", script, re.DOTALL)
    assert attempts_match is not None
    assert interval_match is not None
    return int(attempts_match.group(1)), int(interval_match.group(1))


def _simulate_retry_contract(register_results: list[bool], max_attempts: int) -> tuple[bool, int, bool, bool]:
    immediate_success = bool(register_results and register_results[0])
    if immediate_success:
        return True, 0, False, False

    attempts = 0
    timer_started = True
    timer_cleared = False
    while attempts < max_attempts:
        attempts += 1
        register_ok = register_results[attempts] if attempts < len(register_results) else False
        if register_ok or attempts >= max_attempts:
            timer_cleared = True
            return register_ok, attempts, timer_started, timer_cleared

    return False, attempts, timer_started, timer_cleared


def test_workspaces_last_modified_visible_cell_uses_browser_local_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.ui.pages.workspaces as workspaces_module

    fake_ui = FakeUI()
    install_fake_ui(monkeypatch, workspaces_module, fake_ui, {"access_token": "token"})
    monkeypatch.setattr(workspaces_module, "app_shell", lambda *args, **kwargs: _noop_shell())
    monkeypatch.setattr(workspaces_module, "redirect_if_unauthenticated", lambda **kwargs: False)

    # Use the user-sim timestamp shape with microseconds to guard the regression.
    client_stub = AsyncClientStub(
        [
            httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "ws-1",
                            "name": "Workspace One",
                            "topology_count": 1,
                            "last_modified": "2026-04-12T23:11:18.073315Z",
                        },
                        {
                            "id": "ws-2",
                            "name": "Workspace Two",
                            "topology_count": 0,
                            "last_modified": None,
                        },
                    ]
                },
            ),
        ]
    )
    monkeypatch.setattr(workspaces_module.httpx, "AsyncClient", lambda *args, **kwargs: client_stub)

    asyncio.run(workspaces_module.workspaces_page())

    table = fake_ui.created["table"][0]
    assert table.rows[0]["last_modified"] == "2026-04-12T23:11:18.073315Z"
    assert table.rows[0]["last_modified_display"] == "\u2014"
    assert table.rows[0]["last_modified_display"] != table.rows[0]["last_modified_iso"]
    assert table.rows[0]["last_modified_iso"] == "2026-04-12T23:11:18.073315Z"
    assert table.rows[0]["last_modified_sort"] == "2026-04-12T23:11:18.073315Z"

    assert table.rows[1]["last_modified"] == "\u2014"
    assert table.rows[1]["last_modified_display"] == "\u2014"
    assert table.rows[1]["last_modified_iso"] == ""
    assert table.rows[1]["last_modified_sort"] == ""

    assert "($htFormatLastModifiedLocal && $htFormatLastModifiedLocal(props.row.last_modified_iso, props.row.last_modified_display)) || props.row.last_modified_display" in table.slots["body"]
    assert "<q-tooltip v-if=\"props.row.last_modified_iso\">" in table.slots["body"]
    assert any("window.htFormatLastModifiedLocal" in snippet for snippet in fake_ui.body_html)


def test_last_modified_bridge_registers_formatter_in_vue_global_properties() -> None:
    bridge_script = formatting_module.LAST_MODIFIED_BROWSER_LOCAL_BRIDGE_SCRIPT

    assert "if (!vueApp || !vueApp.config || !vueApp.config.globalProperties)" in bridge_script
    assert "vueApp.config.globalProperties.$htFormatLastModifiedLocal = formatLastModifiedLocal;" in bridge_script


def test_last_modified_bridge_picks_mounted_vue_root_candidate() -> None:
    bridge_script = formatting_module.LAST_MODIFIED_BROWSER_LOCAL_BRIDGE_SCRIPT

    assert "const rootCandidates = [];" in bridge_script
    assert "document.querySelectorAll('[data-v-app]')" in bridge_script
    assert "if (candidate && candidate.__vue_app__)" in bridge_script
    assert "return candidate.__vue_app__;" in bridge_script
    assert "document.querySelector('#app') || document.querySelector('[data-v-app]');" not in bridge_script


def test_last_modified_bridge_retry_contract_succeeds_before_timeout() -> None:
    bridge_script = formatting_module.LAST_MODIFIED_BROWSER_LOCAL_BRIDGE_SCRIPT
    max_attempts, retry_interval_ms = _extract_retry_contract(bridge_script)

    assert re.search(r"if \(registerVueFormatter\(\)\) \{\s*return;", bridge_script, re.DOTALL)
    assert retry_interval_ms == 50

    registered, attempts, timer_started, timer_cleared = _simulate_retry_contract(
        [False, False, True],
        max_attempts,
    )
    assert registered is True
    assert attempts == 2
    assert timer_started is True
    assert timer_cleared is True


def test_last_modified_bridge_retry_contract_times_out_and_clears_interval() -> None:
    bridge_script = formatting_module.LAST_MODIFIED_BROWSER_LOCAL_BRIDGE_SCRIPT
    max_attempts, _ = _extract_retry_contract(bridge_script)

    assert f"if (registerVueFormatter() || attempts >= {max_attempts})" in bridge_script
    assert "clearInterval(retryTimer);" in bridge_script

    registered, attempts, timer_started, timer_cleared = _simulate_retry_contract(
        [False],
        max_attempts,
    )
    assert registered is False
    assert attempts == max_attempts
    assert timer_started is True
    assert timer_cleared is True
