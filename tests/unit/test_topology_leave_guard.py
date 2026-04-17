"""Unit tests for topology in-app leave-guard script injection (HT-074)."""

import pytest

from src.models.types import Role
from tests.unit.nicegui_fakes import FakeUI, install_fake_ui


class TestTopologyLeaveGuard:
    def test_injects_leave_guard_script_for_editors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.topology_leave_guard as leave_guard_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, leave_guard_module, fake_ui)

        leave_guard_module.inject_topology_leave_guard(Role.Contributor.value)

        assert len(fake_ui.body_html) == 1
        script = fake_ui.body_html[0]
        assert "window.htNavigateWithGuard" in script
        assert "Save Version" in script
        assert "Discard" in script
        assert "Cancel" in script
        assert "cancelBtn.addEventListener('click', function(){ closeModal(); });" in script
        assert "/save-version" in script
        assert "/personal-draft" in script

    def test_leave_guard_skips_modal_when_no_unsaved_changes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.topology_leave_guard as leave_guard_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, leave_guard_module, fake_ui)

        leave_guard_module.inject_topology_leave_guard(Role.Admin.value)

        script = fake_ui.body_html[0]
        assert "if (!window._htHasUnsavedChanges)" in script
        assert "window.location.assign(targetUrl);" in script
        assert "if(!hasUnsaved()){ armBypass(); window.history.back(); return; }" in script
        assert "window.history.go(-2)" in script
        assert "window.addEventListener('beforeunload'" in script
        assert "event.returnValue" in script

    def test_leave_guard_intercepts_internal_nav_before_native_unload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.topology_leave_guard as leave_guard_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, leave_guard_module, fake_ui)

        leave_guard_module.inject_topology_leave_guard(Role.Contributor.value)

        script = fake_ui.body_html[0]
        assert "[data-ht-guard-nav]" in script
        assert "data-ht-nav-target" in script
        assert "getEventTargetElement" in script
        assert "event.composedPath" in script
        assert "window.addEventListener('click'" in script
        assert "event.stopImmediatePropagation" in script
        assert "event.stopPropagation" in script
        assert "window.addEventListener('pointerdown'" in script
        assert "window.addEventListener('mousedown'" in script
        assert "window.addEventListener('touchstart'" in script
        assert "pointerTargetUrl" in script
        assert "window.htNavigateWithGuard(pointerTargetUrl);" in script
        assert "if(event.defaultPrevented) return;" not in script
        assert "consumeNavEvent(event);" in script
        assert "window.htNavigateWithGuard(markedUrl);" in script
        assert "[data-ht-nav-target],[data-ht-guard-nav]" in script
        assert "hasAttribute('data-ht-nav-target')" in script
        assert "window.addEventListener('popstate'" in script
        assert "var HISTORY_BACK_TOKEN = '__ht-history-back__'" in script
        assert "window.history.replaceState" in script
        assert "window.history.pushState" in script
        assert "openModal(HISTORY_BACK_TOKEN);" in script
        assert "window._htUserRole === 'Admin'" not in script

    def test_reader_does_not_receive_leave_guard_script(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.topology_leave_guard as leave_guard_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, leave_guard_module, fake_ui)

        leave_guard_module.inject_topology_leave_guard(Role.Reader.value)

        assert fake_ui.body_html == []
