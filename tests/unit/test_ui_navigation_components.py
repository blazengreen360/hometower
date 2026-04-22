"""Execution tests for shell and navigation components."""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from src.models.types import Role
from tests.unit.nicegui_fakes import FakeUI, install_fake_ui


async def _invoke(handler: Callable[..., object]) -> object:
    result = handler()
    if inspect.isawaitable(result):
        return await result
    return result


@contextmanager
def _noop_shell() -> Iterator[None]:
    yield


class TestAppShell:
    def test_app_shell_renders_header_user_menu_and_theme_change(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.app_shell as app_shell_module

        fake_ui = FakeUI()
        install_fake_ui(
            monkeypatch,
            app_shell_module,
            fake_ui,
            {"username": "alice", "theme": "dark", "sidebar_expanded": True},
        )
        monkeypatch.setattr(app_shell_module, "render_sidebar", lambda current_route: None)
        monkeypatch.setattr(app_shell_module, "get_initial_theme_css", lambda theme: f"css:{theme}")
        monkeypatch.setattr(app_shell_module, "get_theme_js_helpers", lambda: "theme-helpers")
        applied_themes: list[str] = []

        async def fake_apply_theme_to_client(theme: str) -> None:
            applied_themes.append(theme)

        monkeypatch.setattr(app_shell_module, "apply_theme_to_client", fake_apply_theme_to_client)

        with app_shell_module.app_shell(
            "Dashboard",
            "/dashboard",
            breadcrumb=["Dashboard", "Overview"],
            header_actions=lambda: fake_ui.button("Action"),
        ):
            fake_ui.label("Body")

        assert "css:dark" in fake_ui.head_html
        assert "theme-helpers" in fake_ui.head_html
        assert any("ht-ui-primitives" in html for html in fake_ui.head_html)
        assert fake_ui.body_html
        assert any(link.value == "Hometower" for link in fake_ui.created["link"])
        assert any(label.text_value == "Dashboard" for label in fake_ui.created["label"])
        assert any(label.text_value == "Overview" for label in fake_ui.created["label"])
        assert any(button.value == "Action" for button in fake_ui.created["button"])

        theme_item = next(item for item in fake_ui.created["item"] if item.value.endswith("Light"))
        logout_item = next(item for item in fake_ui.created["item"] if item.value == "Logout")

        asyncio.run(_invoke(theme_item.handlers["click"]))
        assert app_shell_module.nicegui_app.storage.user["theme"] == "light"
        assert applied_themes == ["light"]
        assert any("updateCyTheme" in code for code in fake_ui.run_javascript_calls)

        asyncio.run(_invoke(logout_item.handlers["click"]))
        assert app_shell_module.nicegui_app.storage.user == {}
        assert fake_ui.navigate.to_calls[-1] == ("/login", False)

    def test_app_shell_renders_header_sidebar_affordance_from_sidebar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.app_shell as app_shell_module
        import src.ui.components.sidebar as sidebar_module

        fake_ui = FakeUI()
        install_fake_ui(
            monkeypatch,
            app_shell_module,
            fake_ui,
            {"username": "alice", "theme": "dark", "sidebar_expanded": True},
        )
        monkeypatch.setattr(app_shell_module, "get_initial_theme_css", lambda theme: f"css:{theme}")
        monkeypatch.setattr(app_shell_module, "get_theme_js_helpers", lambda: "theme-helpers")

        opened: dict[str, int] = {"count": 0}

        def _open_drawer() -> None:
            opened["count"] += 1

        monkeypatch.setattr(
            app_shell_module,
            "render_sidebar",
            lambda current_route: sidebar_module.SidebarControls(
                open_drawer=_open_drawer,
                expand_sidebar=_open_drawer,
            ),
        )

        with app_shell_module.app_shell("Dashboard", "/dashboard"):
            fake_ui.label("Body")

        menu_button = next(button for button in fake_ui.created["button"] if button.value == "menu")
        menu_button.click()

        assert opened["count"] == 1
        assert any("ht-sidebar-reopen" in classes for classes in menu_button.classes_calls)

    def test_app_shell_renders_sidebar_reopen_button_when_controls_support_expand(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.app_shell as app_shell_module
        import src.ui.components.sidebar as sidebar_module

        fake_ui = FakeUI()
        install_fake_ui(
            monkeypatch,
            app_shell_module,
            fake_ui,
            {"username": "alice", "theme": "dark", "sidebar_expanded": False},
        )
        monkeypatch.setattr(app_shell_module, "get_initial_theme_css", lambda theme: f"css:{theme}")
        monkeypatch.setattr(app_shell_module, "get_theme_js_helpers", lambda: "theme-helpers")

        calls: dict[str, int] = {"open": 0, "expand": 0}

        monkeypatch.setattr(
            app_shell_module,
            "render_sidebar",
            lambda current_route: sidebar_module.SidebarControls(
                open_drawer=lambda: calls.__setitem__("open", calls["open"] + 1),
                expand_sidebar=lambda: calls.__setitem__("expand", calls["expand"] + 1),
            ),
        )

        with app_shell_module.app_shell("Topology", "/topology"):
            fake_ui.label("Body")

        affordance_button = next(button for button in fake_ui.created["button"] if button.value == "menu")

        affordance_button.click()

        assert calls == {"open": 1, "expand": 0}
        assert any("ht-sidebar-reopen" in classes for classes in affordance_button.classes_calls)


class TestSidebar:
    def test_render_sidebar_admin_shows_users_and_toggle(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.sidebar as sidebar_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, sidebar_module, fake_ui, {"sidebar_expanded": True})
        monkeypatch.setattr(sidebar_module, "get_ui_role", lambda: Role.Admin)

        sidebar_module.render_sidebar("/settings/users")

        labels = [label.text_value for label in fake_ui.created["label"]]
        assert "Networks" in labels
        assert "Power" in labels
        assert "Users" in labels
        assert "Map" in labels
        assert fake_ui.created["badge"] == []

        collapse_button = fake_ui.created["button"][0]
        collapse_button.click()
        assert sidebar_module.nicegui_app.storage.user["sidebar_expanded"] is False
        drawer = fake_ui.created["left_drawer"][0]
        assert drawer.toggled is False
        assert any('icon="chevron_right"' in props for props in collapse_button.props_calls)
        assert any("mini" in props for props in drawer.props_calls)

        dashboard_row = fake_ui.created["row"][1]
        dashboard_row.click()
        assert fake_ui.navigate.to_calls[-1] == ("/", False)

    def test_render_sidebar_reader_hides_admin_only_item(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.sidebar as sidebar_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, sidebar_module, fake_ui, {"sidebar_expanded": False})
        monkeypatch.setattr(sidebar_module, "get_ui_role", lambda: Role.Reader)

        sidebar_module.render_sidebar("/")

        labels = [label.text_value for label in fake_ui.created["label"]]
        assert "Networks" in labels
        assert "Power" not in labels
        assert "Users" not in labels
        assert "Settings" in labels
        assert fake_ui.created["button"][0].value == "chevron_right"

    def test_render_sidebar_sets_mobile_safe_drawer_initial_state(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.sidebar as sidebar_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, sidebar_module, fake_ui, {"sidebar_expanded": True})
        monkeypatch.setattr(sidebar_module, "get_ui_role", lambda: Role.Reader)

        sidebar_module.render_sidebar("/inventory")

        drawer = fake_ui.created["left_drawer"][0]
        all_props = " ".join(drawer.props_calls)
        assert drawer.value is False
        assert "show-if-above" in all_props
        assert "breakpoint=768" in all_props

    def test_render_sidebar_returns_mobile_open_callback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.sidebar as sidebar_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, sidebar_module, fake_ui, {"sidebar_expanded": True})
        monkeypatch.setattr(sidebar_module, "get_ui_role", lambda: Role.Reader)

        open_drawer = sidebar_module.render_sidebar("/inventory")
        drawer = fake_ui.created["left_drawer"][0]

        assert drawer.toggled is False
        open_drawer()
        assert drawer.toggled is True

    def test_render_sidebar_returns_controls_that_can_reopen_collapsed_sidebar(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.sidebar as sidebar_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, sidebar_module, fake_ui, {"sidebar_expanded": False})
        monkeypatch.setattr(sidebar_module, "get_ui_role", lambda: Role.Reader)

        controls = sidebar_module.render_sidebar("/inventory")
        drawer = fake_ui.created["left_drawer"][0]
        toggle_button = fake_ui.created["button"][0]
        sync_source = inspect.getsource(sidebar_module._sync_sidebar_state)

        assert "ht-sidebar-collapsed" in sync_source
        assert "ht:topology-layout-sync" in sync_source

        controls.expand_sidebar()

        assert sidebar_module.nicegui_app.storage.user["sidebar_expanded"] is True
        assert any('icon="chevron_left"' in props for props in toggle_button.props_calls)
        assert any("mini=false" in props for props in drawer.props_calls)

    def test_render_sidebar_controls_call_reopens_collapsed_sidebar_and_drawer(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.sidebar as sidebar_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, sidebar_module, fake_ui, {"sidebar_expanded": False})
        monkeypatch.setattr(sidebar_module, "get_ui_role", lambda: Role.Reader)

        controls = sidebar_module.render_sidebar("/inventory")
        drawer = fake_ui.created["left_drawer"][0]
        toggle_button = fake_ui.created["button"][0]

        assert drawer.value is False

        controls()

        assert sidebar_module.nicegui_app.storage.user["sidebar_expanded"] is True
        assert drawer.value is True
        assert any('icon="chevron_left"' in props for props in toggle_button.props_calls)
        assert any("mini=false" in props for props in drawer.props_calls)

    def test_render_topology_left_rail_uses_consolidated_expansions(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.topology_layout_shell as layout_shell_module

        fake_ui = FakeUI()
        monkeypatch.setattr(layout_shell_module, "ui", fake_ui)
        monkeypatch.setattr(layout_shell_module, "render_palette", lambda: fake_ui.label("Palette"))
        monkeypatch.setattr(
            layout_shell_module,
            "render_stencils_panel",
            lambda stencil_devices, placed_ids: fake_ui.label("Inventory"),
        )

        rail = layout_shell_module.render_topology_left_rail([], set())
        labels = [label.text_value for label in fake_ui.created["label"]]

        assert any('id="ht-topology-left-rail"' in props for props in rail.props_calls)
        assert len(fake_ui.created["expansion"]) == 2
        assert "Tool Rail" not in labels
        assert "Edit-mode tools stay tucked away until you need them." not in labels
        assert rail.visible is False

    def test_render_topology_left_rail_defaults_to_single_open_section_and_compacts_when_collapsed(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.topology_layout_shell as layout_shell_module

        fake_ui = FakeUI()
        monkeypatch.setattr(layout_shell_module, "ui", fake_ui)
        monkeypatch.setattr(layout_shell_module, "render_palette", lambda: fake_ui.label("Palette"))
        monkeypatch.setattr(
            layout_shell_module,
            "render_stencils_panel",
            lambda stencil_devices, placed_ids: fake_ui.label("Inventory"),
        )

        sync_calls: list[str] = []
        monkeypatch.setattr(
            layout_shell_module,
            "trigger_topology_layout_sync",
            lambda: sync_calls.append("sync"),
        )

        rail = layout_shell_module.render_topology_left_rail([], set())
        expansions = fake_ui.created["expansion"]

        assert [expansion.value for expansion in expansions] == [True, False]

        expansions[0].handlers["value_change"](SimpleNamespace(value=False))

        assert any(classes == "add:ht-topology-left-rail--compact" for classes in rail.classes_calls)
        assert sync_calls == ["sync"]

    def test_render_sidebar_uses_leave_guard_bridge_on_topology_route(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.sidebar as sidebar_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, sidebar_module, fake_ui, {"sidebar_expanded": True})
        monkeypatch.setattr(sidebar_module, "get_ui_role", lambda: Role.Contributor)

        sidebar_module.render_sidebar("/topology")

        dashboard_row = fake_ui.created["row"][1]
        assert fake_ui.navigate.to_calls == []
        assert any('data-ht-guard-nav="true"' in prop for prop in dashboard_row.props_calls)
        assert any('data-ht-nav-target="/"' in prop for prop in dashboard_row.props_calls)
        inventory_label = next(label for label in fake_ui.created["label"] if label.text_value == "Inventory")
        assert any('data-ht-guard-nav="true"' in prop for prop in inventory_label.props_calls)
        assert any('data-ht-nav-target="/inventory"' in prop for prop in inventory_label.props_calls)
        assert any("pointer-events:none" in style for style in inventory_label.style_calls)
        assert "click" not in dashboard_row.handlers
        assert "click" not in dashboard_row.js_handlers

    def test_render_sidebar_topology_route_clears_active_style_from_nav_items(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import src.ui.components.sidebar as sidebar_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, sidebar_module, fake_ui, {"sidebar_expanded": True})
        monkeypatch.setattr(sidebar_module, "get_ui_role", lambda: Role.Reader)

        sidebar_module.render_sidebar("/topology")

        map_row = fake_ui.created["row"][5]
        map_styles = " ".join(map_row.style_calls)

        assert "background-color:transparent" in map_styles
        assert "border-left:3px solid transparent" in map_styles
        assert "var(--ht-accent-glow)" not in map_styles


class TestBreadcrumb:
    def test_render_breadcrumb_renders_links_and_current_label(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.breadcrumb as breadcrumb_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, breadcrumb_module, fake_ui)

        breadcrumb_module.render_breadcrumb(
            [
                ("Workspaces", "/workspaces"),
                ("Alpha", "/workspaces/alpha"),
                ("Topology", "/workspaces/alpha/topology"),
            ]
        )

        assert [link.value for link in fake_ui.created["link"]] == ["Workspaces", "Alpha"]
        labels = [label.text_value for label in fake_ui.created["label"]]
        assert "Topology" in labels
        assert labels.count("/") == 2

    def test_render_breadcrumb_can_use_topology_leave_guard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.ui.components.breadcrumb as breadcrumb_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, breadcrumb_module, fake_ui)

        breadcrumb_module.render_breadcrumb(
            [
                ("Workspaces", "/workspaces"),
                ("Alpha", "/workspaces/alpha"),
                ("Topology", ""),
            ],
            use_leave_guard=True,
        )

        clickable_rows = [row for row in fake_ui.created["row"] if "click" in row.handlers]
        assert clickable_rows == []
        js_clickable_rows = [row for row in fake_ui.created["row"] if "click" in row.js_handlers]
        assert js_clickable_rows == []
        guard_rows = [
            row
            for row in fake_ui.created["row"]
            if any('data-ht-guard-nav="true"' in prop for prop in row.props_calls)
        ]
        assert len(guard_rows) == 2
        first_row = guard_rows[0]
        assert any('data-ht-guard-nav="true"' in prop for prop in first_row.props_calls)
        assert any('data-ht-nav-target="/workspaces"' in prop for prop in first_row.props_calls)
        workspaces_label = next(label for label in fake_ui.created["label"] if label.text_value == "Workspaces")
        assert any('data-ht-guard-nav="true"' in prop for prop in workspaces_label.props_calls)
        assert any('data-ht-nav-target="/workspaces"' in prop for prop in workspaces_label.props_calls)
        assert any("pointer-events:none" in style for style in workspaces_label.style_calls)
        assert fake_ui.navigate.to_calls == []
        assert fake_ui.run_javascript_calls == []
