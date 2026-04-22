"""Shared callable types for canvas undo dispatch helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx

ResolveSuccess = Callable[[str, str, dict[str, object]], Awaitable[None]]
ResolveFailure = Callable[[str, str, str], Awaitable[None]]
CallApi = Callable[[str, str, dict[str, object] | None], Awaitable[httpx.Response]]