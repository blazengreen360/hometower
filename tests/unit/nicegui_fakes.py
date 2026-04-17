"""Shared NiceGUI test doubles for page/component execution tests."""
from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace
from typing import Callable, Iterator

import pytest


@dataclass
class FakeResponse:
    status_code: int
    payload: dict[str, object] | list[object] | None = None
    text: str = ""
    headers: dict[str, str] | None = None

    def json(self) -> dict[str, object] | list[object]:
        if self.payload is None:
            return {}
        return self.payload


class AsyncClientStub:
    """Very small httpx.AsyncClient replacement that returns queued responses."""

    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []
        self.call_kwargs: list[dict[str, object]] = []

    async def __aenter__(self) -> "AsyncClientStub":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def _next(self, method: str, url: str, kwargs: dict[str, object]) -> FakeResponse:
        self.calls.append((method, url))
        self.call_kwargs.append(dict(kwargs))
        if not self.responses:
            raise AssertionError(f"No queued response for {method} {url}")
        next_item = self.responses.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        return next_item

    async def get(self, url: str, **kwargs: object) -> FakeResponse:
        return self._next("GET", url, dict(kwargs))

    async def post(self, url: str, **kwargs: object) -> FakeResponse:
        return self._next("POST", url, dict(kwargs))

    async def patch(self, url: str, **kwargs: object) -> FakeResponse:
        return self._next("PATCH", url, dict(kwargs))

    async def put(self, url: str, **kwargs: object) -> FakeResponse:
        return self._next("PUT", url, dict(kwargs))

    async def delete(self, url: str, **kwargs: object) -> FakeResponse:
        return self._next("DELETE", url, dict(kwargs))


class FakeNavigate:
    def __init__(self) -> None:
        self.to_calls: list[tuple[str, bool]] = []
        self.reload_calls = 0

    def to(self, url: str, new_tab: bool = False) -> None:
        self.to_calls.append((url, new_tab))

    def reload(self) -> None:
        self.reload_calls += 1


class FakeElement:
    _counter = 0

    def __init__(self, kind: str, value: object = None) -> None:
        FakeElement._counter += 1
        self.kind = kind
        self.id = FakeElement._counter
        self._value = value
        self.bound_mapping: dict[str, object] | None = None
        self.bound_key: str | None = None
        self.props_calls: list[str] = []
        self.style_calls: list[str] = []
        self.classes_calls: list[str] = []
        self.handlers: dict[str, Callable[..., object]] = {}
        self.js_handlers: dict[str, str] = {}
        self.rows: list[dict[str, object]] = []
        self.columns: list[dict[str, object]] = []
        self.row_key: str | None = None
        self.selection: str | None = None
        self.selected: list[dict[str, object]] = []
        self.slots: dict[str, str] = {}
        self.options: object = None
        self.opened = False
        self.closed = False
        self.visible = True
        self.toggled = False
        self.text_value = str(value) if value is not None else ""

    @property
    def value(self) -> object:
        return self._value

    @value.setter
    def value(self, new_value: object) -> None:
        self._value = new_value
        if self.bound_mapping is not None and self.bound_key is not None:
            self.bound_mapping[self.bound_key] = new_value

    def __enter__(self) -> "FakeElement":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def classes(
        self,
        classes: str | None = None,
        *,
        add: str | None = None,
        remove: str | None = None,
        replace: str | None = None,
        toggle: str | None = None,
    ) -> "FakeElement":
        if classes is not None:
            self.classes_calls.append(classes)
        if add is not None:
            self.classes_calls.append(f"add:{add}")
        if remove is not None:
            self.classes_calls.append(f"remove:{remove}")
        if replace is not None:
            self.classes_calls.append(f"replace:{replace}")
        if toggle is not None:
            self.classes_calls.append(f"toggle:{toggle}")
        return self

    def style(self, style: str) -> "FakeElement":
        self.style_calls.append(style)
        return self

    def props(self, *args: object, **kwargs: object) -> "FakeElement":
        if args:
            self.props_calls.extend(str(arg) for arg in args)
        if kwargs:
            self.props_calls.append(repr(kwargs))
        return self

    def on(
        self,
        event_name: str,
        handler: Callable[..., object] | None = None,
        *_args: object,
        js_handler: str = "(...args) => emit(...args)",
        **_kwargs: object,
    ) -> "FakeElement":
        if handler is not None:
            self.handlers[event_name] = handler
        if js_handler != "(...args) => emit(...args)":
            self.js_handlers[event_name] = js_handler
        return self

    def on_value_change(self, handler: Callable[..., object]) -> "FakeElement":
        return self.on("value_change", handler)

    def bind_value(self, mapping: dict[str, object], key: str) -> "FakeElement":
        self.bound_mapping = mapping
        self.bound_key = key
        self.value = mapping[key]
        return self

    def set_value(self, value: object) -> None:
        self.value = value

    def set_text(self, text: str) -> None:
        self.text_value = text

    def set_visibility(self, visible: bool) -> None:
        self.visible = visible

    def add_slot(self, name: str, slot: str) -> None:
        self.slots[name] = slot

    def set_options(self, options: object, value: object | None = None) -> None:
        self.options = options
        if value is not None:
            self.value = value

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.closed = True

    def toggle(self) -> None:
        self.toggled = not self.toggled

    def update(self) -> None:
        return None

    def update_rows(self, rows: list[dict[str, object]], clear_selection: bool = False) -> None:
        self.rows = list(rows)
        if clear_selection:
            self.selected = []
        self.update()

    def clear(self) -> None:
        return None

    def trigger(self, event_name: str, *args: object, **kwargs: object) -> object:
        handler = self.handlers[event_name]
        payload = kwargs or (args[0] if args else {})
        return handler(SimpleNamespace(args=payload))

    def click(self) -> object:
        handler = self.handlers.get("click")
        if handler is None:
            raise AssertionError(f"No click handler registered for {self.kind}")
        return handler()


class FakeUI:
    def __init__(self) -> None:
        self.navigate = FakeNavigate()
        self.head_html: list[str] = []
        self.body_html: list[str] = []
        self.notifications: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.run_javascript_calls: list[str] = []
        self.run_javascript_responses: list[object] = []
        self.timer_calls: list[tuple[float, Callable[[], object], bool]] = []
        self.pending_tasks: list[asyncio.Future[object] | asyncio.Task[object]] = []
        self.created: dict[str, list[FakeElement]] = defaultdict(list)
        self.on_handlers: dict[str, Callable[..., object]] = {}

    def _element(self, kind: str, value: object = None) -> FakeElement:
        element = FakeElement(kind, value=value)
        self.created[kind].append(element)
        return element

    def add_head_html(self, html: str) -> None:
        self.head_html.append(html)

    def add_body_html(self, html: str) -> None:
        self.body_html.append(html)

    def query(self, _selector: str) -> FakeElement:
        return self._element("query")

    def row(self, *_args: object, **_kwargs: object) -> FakeElement:
        return self._element("row")

    def column(self, *_args: object, **_kwargs: object) -> FakeElement:
        return self._element("column")

    def card(self, *_args: object, **_kwargs: object) -> FakeElement:
        return self._element("card")

    def expansion(self, *args: object, value: object = None, **_kwargs: object) -> FakeElement:
        title = args[0] if args else None
        return self._element("expansion", value=value if value is not None else title)

    def header(self, *_args: object, **_kwargs: object) -> FakeElement:
        return self._element("header")

    def left_drawer(self, *_args: object, **_kwargs: object) -> FakeElement:
        return self._element("left_drawer", value=_kwargs.get("value"))

    def dialog(self, *_args: object, **_kwargs: object) -> FakeElement:
        return self._element("dialog")

    def element(self, *_args: object, **_kwargs: object) -> FakeElement:
        return self._element("element")

    def dropdown_button(self, value: object = None, **_kwargs: object) -> FakeElement:
        return self._element("dropdown_button", value=value)

    def button(self, value: object = None, *, icon: str | None = None, on_click: Callable[..., object] | None = None, **_kwargs: object) -> FakeElement:
        element = self._element("button", value=value or icon)
        if on_click is not None:
            element.handlers["click"] = on_click
        return element

    def item(self, value: object = None, *, on_click: Callable[..., object] | None = None, **_kwargs: object) -> FakeElement:
        element = self._element("item", value=value)
        if on_click is not None:
            element.handlers["click"] = on_click
        return element

    def label(self, value: object = None, **_kwargs: object) -> FakeElement:
        return self._element("label", value=value)

    def icon(self, value: object = None, **_kwargs: object) -> FakeElement:
        return self._element("icon", value=value)

    def link(self, value: object = None, *_args: object, **_kwargs: object) -> FakeElement:
        return self._element("link", value=value)

    def badge(self, value: object = None, **_kwargs: object) -> FakeElement:
        return self._element("badge", value=value)

    def separator(self, *_args: object, **_kwargs: object) -> FakeElement:
        return self._element("separator")

    def space(self) -> FakeElement:
        return self._element("space")

    def input(self, *args: object, label: str | None = None, value: object = "", placeholder: str = "", **_kwargs: object) -> FakeElement:
        return self._element("input", value=value)

    def textarea(self, *args: object, label: str | None = None, value: object = "", **_kwargs: object) -> FakeElement:
        return self._element("textarea", value=value)

    def select(self, options: object = None, *, label: str | None = None, value: object = None, **_kwargs: object) -> FakeElement:
        element = self._element("select", value=value)
        element.options = options
        return element

    def checkbox(self, value: object = None, *, on_change: Callable[..., object] | None = None, **_kwargs: object) -> FakeElement:
        element = self._element("checkbox", value=False if value is None else value)
        if on_change is not None:
            element.handlers["change"] = on_change
        return element

    def upload(self, *args: object, label: str | None = None, on_upload: Callable[..., object] | None = None, **_kwargs: object) -> FakeElement:
        element = self._element("upload")
        if on_upload is not None:
            element.handlers["upload"] = on_upload
        return element

    def table(
        self,
        *,
        columns: list[dict[str, object]] | None = None,
        rows: list[dict[str, object]] | None = None,
        row_key: str | None = None,
        selection: str | None = None,
        on_select: Callable[..., object] | None = None,
        **_kwargs: object,
    ) -> FakeElement:
        element = self._element("table")
        element.columns = list(columns or [])
        element.rows = list(rows or [])
        element.row_key = row_key
        element.selection = selection
        if on_select is not None:
            element.handlers["select"] = on_select
        return element

    def linear_progress(self, value: float = 0.0, **_kwargs: object) -> FakeElement:
        return self._element("linear_progress", value=value)

    def timer(self, delay: float, callback: Callable[[], object], once: bool = False) -> FakeElement:
        self.timer_calls.append((delay, callback, once))
        result = callback()
        if inspect.isawaitable(result):
            if asyncio.isfuture(result):
                self.pending_tasks.append(result)  # type: ignore[arg-type]
            else:
                self.pending_tasks.append(asyncio.create_task(result))
        return self._element("timer")

    async def run_javascript(self, code: str) -> object:
        self.run_javascript_calls.append(code)
        if not self.run_javascript_responses:
            return None
        response = self.run_javascript_responses.pop(0)
        return response(code) if callable(response) else response

    def notify(self, *args: object, **kwargs: object) -> None:
        self.notifications.append((args, kwargs))

    def on(self, event_name: str, handler: Callable[..., object]) -> None:
        self.on_handlers[event_name] = handler


@contextmanager
def noop_context() -> Iterator[None]:
    yield


def make_fake_app(user: dict[str, object] | None = None) -> SimpleNamespace:
    return SimpleNamespace(storage=SimpleNamespace(user=user or {}))


def install_fake_ui(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    fake_ui: FakeUI,
    user: dict[str, object] | None = None,
) -> SimpleNamespace:
    fake_app = make_fake_app(user)
    monkeypatch.setattr(module, "ui", fake_ui)
    monkeypatch.setattr(module, "nicegui_app", fake_app, raising=False)
    return fake_app
