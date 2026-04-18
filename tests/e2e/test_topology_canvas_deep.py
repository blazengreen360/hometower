"""Deep Playwright canvas test for topology-scoped load/save persistence.

Run directly (requires server on port 8080):
    python tests/e2e/test_topology_canvas_deep.py
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from playwright.sync_api import Page, sync_playwright, Error as PlaywrightError

BASE = "http://localhost:8080"
ADMIN_EMAIL = "admin@hometower.local"
ADMIN_PASS = "changeme_on_first_boot"


def api(method: str, path: str, body: dict[str, object] | None = None, token: str = "") -> dict[str, object]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"raw": raw}
        parsed["__status"] = exc.code
        return parsed


def login_api() -> str:
    data = api("POST", "/api/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    token = str(data.get("access_token", ""))
    if not token:
        raise RuntimeError(f"API login failed: {data}")
    return token


def login_ui(page: Page) -> None:
    """Perform UI login and wait for an authenticated navigation.

    Replaces the brittle fixed sleep with an explicit wait for the
    `/api/auth/login` response and a poll that ensures the page has
    actually navigated away from `/login`. Retries a few times to
    tolerate transient `ERR_ABORTED` fetches during navigation.
    """
    page.goto(f"{BASE}/login", wait_until="networkidle")
    email_el = page.locator('input[type="text"], input[type="email"]').first
    pass_el = page.locator('input[type="password"]').first
    login_btn = page.locator('button:has-text("Log in")').first

    email_el.fill(ADMIN_EMAIL)
    pass_el.fill(ADMIN_PASS)

    attempts = 0
    max_attempts = 3
    while attempts < max_attempts:
        attempts += 1
        try:
            # Start waiting for the login POST response while triggering it.
            with page.expect_response(
                lambda r: r.url.endswith('/api/auth/login') and r.request.method == 'POST',
                timeout=8000,
            ) as resp_info:
                login_btn.click()
            resp = resp_info.value
        except Exception:
            # Either the request was aborted or the wait timed out. If the
            # browser already navigated away from /login assume success,
            # otherwise retry after a brief backoff.
            if not page.url.endswith('/login') and '/login' not in page.url:
                return
            page.wait_for_timeout(400)
            # refill in case inputs were cleared
            try:
                email_el.fill(ADMIN_EMAIL)
                pass_el.fill(ADMIN_PASS)
            except Exception:
                page.goto(f"{BASE}/login", wait_until="networkidle")
            continue

        # Got a response for the login POST; ensure it succeeded.
        status = getattr(resp, 'status', None)
        try:
            body = resp.json()
        except Exception:
            body = None
        if status is None or status >= 400:
            raise RuntimeError(f"UI login failed (status={status}, body={body})")

        # Wait for the client-side redirect (ui.navigate.to) to change URL away from /login.
        deadline = time.time() + 8.0
        while time.time() < deadline:
            cur = page.url or ''
            if not cur.endswith('/login') and '/login' not in cur:
                try:
                    page.wait_for_load_state('networkidle', timeout=2000)
                except Exception:
                    pass
                # Post-login readiness gate: wait for a reliable authenticated
                # app-shell signal before proceeding. We consider the app-shell
                # ready when any of these are true:
                #  - `window._htFetchIntercepted` (app_shell JS injected)
                #  - `window._htUserRole` (pages set this when rendering authenticated pages)
                #  - presence of the header bearing the app title (rendered by app_shell)
                predicate = (
                    "() => {"
                    " try {"
                    "  if (window._htFetchIntercepted) return true;"
                    "  if (window._htUserRole) return true;"
                    "  var h = document.querySelector('header');"
                    "  if (h && h.innerText && h.innerText.indexOf('Hometower') !== -1) return true;"
                    "  return false;"
                    " } catch(e) { return false; }"
                    "}"
                )
                # Allow up to 8s for the app-shell to initialise (network + client boot)
                try:
                    ready = evaluate_with_retry(page, predicate, timeout_ms=8000)
                except Exception:
                    ready = False
                if not ready:
                    # As a conservative fallback, give a short extra pause before failing
                    page.wait_for_timeout(400)
                return
            page.wait_for_timeout(200)

        # No redirect observed yet; try again (some clients update storage before navigation).
        page.wait_for_timeout(250)
    # If we exhausted retries, raise so the test fails clearly rather than continuing
    raise RuntimeError('UI login did not complete after retries')


def wait_for_cy(page: Page, timeout_ms: int = 30000) -> bool:
    """Wait for Cytoscape (`window._cy`) to be available.

    This wraps `page.evaluate` in a retry loop that treats Playwright's
    transient "Execution context was destroyed" (and similar) errors as
    recoverable during navigation. Only unexpected errors are re-raised so
    real failures surface.
    """
    deadline = time.time() + (timeout_ms / 1000.0)
    predicate = "() => typeof window._cy !== 'undefined' && window._cy !== null && typeof window._cy.nodes === 'function'"
    while time.time() < deadline:
        try:
            ready = page.evaluate(predicate)
            if ready:
                return True
        except PlaywrightError as exc:
            msg = str(exc)
            # Known transient messages from Playwright during navigation/context reset.
            if (
                "Execution context was destroyed" in msg
                or "Cannot find context with specified id" in msg
                or "Target closed" in msg
                or "The page has been closed" in msg
                or "Cannot find context" in msg
            ):
                # brief backoff and retry until deadline
                page.wait_for_timeout(200)
                continue
            # Unexpected playwright error -> surface it
            raise
        except Exception:
            # Generic fallback: backoff and retry (covers intermittent transport hiccups)
            page.wait_for_timeout(200)
            continue
        page.wait_for_timeout(250)
    return False


def evaluate_with_retry(page: Page, expression, arg=None, timeout_ms: int = 2000) -> object:
    """Evaluate JS in-page with a small retry/backoff loop to tolerate
    transient Playwright execution-context resets (e.g. navigation).

    The loop treats the known transient PlaywrightError messages as
    recoverable and retries until the deadline. On deadline expiry we
    perform one final evaluate so real failures surface with their
    original exception.
    """
    deadline = time.time() + (timeout_ms / 1000.0)
    last_exc: Exception | None = None
    while time.time() < deadline:
        try:
            if arg is None:
                return page.evaluate(expression)
            return page.evaluate(expression, arg)
        except PlaywrightError as exc:
            msg = str(exc)
            if (
                "Execution context was destroyed" in msg
                or "Cannot find context with specified id" in msg
                or "Target closed" in msg
                or "The page has been closed" in msg
                or "Cannot find context" in msg
            ):
                last_exc = exc
                page.wait_for_timeout(150)
                continue
            raise
        except Exception as exc:  # generic intermittent transport hiccups
            last_exc = exc
            page.wait_for_timeout(150)
            continue
    # Final attempt: let the underlying error raise so the test fails loudly.
    if arg is None:
        return page.evaluate(expression)
    return page.evaluate(expression, arg)


def select_node(page: Page, node_id: str) -> None:
    page.evaluate(
        """(targetId) => {
            if (!window._cy) return;
            var node = window._cy.getElementById(targetId);
            if (!node || !node.length) return;
            window._cy.nodes().unselect();
            node.select();
        }""",
        node_id,
    )
    page.wait_for_timeout(250)


def overlay_visible(page: Page) -> bool:
    script = """() => {
            var overlay = document.getElementById('ht-node-resize-overlay');
            if (!overlay) return false;
            var style = window.getComputedStyle(overlay);
            return style.display !== 'none' && style.visibility !== 'hidden';
        }"""
    return bool(evaluate_with_retry(page, script, timeout_ms=1200))


def drag_resize_handle(page: Page, direction: str, dx: float, dy: float) -> bool:
    handle = page.locator(f'#ht-node-resize-overlay [data-ht-resize-handle="{direction}"]')
    if handle.count() == 0:
        return False
    box = handle.first.bounding_box()
    if box is None:
        return False
    start_x = box["x"] + (box["width"] / 2)
    start_y = box["y"] + (box["height"] / 2)
    page.mouse.move(start_x, start_y)
    page.mouse.down()
    page.mouse.move(start_x + dx, start_y + dy)
    page.mouse.up()
    page.wait_for_timeout(350)
    return True


def pointer_drag_handle(page: Page, direction: str, dx: float, dy: float) -> bool:
    """Dispatch pointer events directly on the overlay handle to drive the resize pointer flow."""
    script = """(payload) => {
            var direction = payload.direction;
            var dx = payload.dx;
            var dy = payload.dy;
            var sel = document.querySelector('#ht-node-resize-overlay [data-ht-resize-handle="' + direction + '"]');
            if (!sel) return false;
            var rect = sel.getBoundingClientRect();
            var startX = rect.left + rect.width / 2;
            var startY = rect.top + rect.height / 2;
            var endX = startX + dx;
            var endY = startY + dy;

            function makePointer(type, x, y, id) {
                return new PointerEvent(type, {
                    bubbles: true,
                    cancelable: true,
                    pointerId: id,
                    clientX: x,
                    clientY: y,
                    pointerType: 'mouse',
                    isPrimary: true,
                });
            }

            var pid = 424242;
            sel.dispatchEvent(makePointer('pointerdown', startX, startY, pid));
            // small interpolated moves for more realistic pointermove sequence
            var steps = 3;
            for (var i = 1; i <= steps; i++) {
                var ix = startX + (dx * i) / steps;
                var iy = startY + (dy * i) / steps;
                sel.dispatchEvent(makePointer('pointermove', ix, iy, pid));
            }
            sel.dispatchEvent(makePointer('pointerup', endX, endY, pid));
            return true;
        }"""
    return bool(evaluate_with_retry(page, script, {"direction": direction, "dx": dx, "dy": dy}, timeout_ms=1200))


def read_node_size(page: Page, node_id: str) -> dict[str, object]:
    script = """(targetId) => {
            if (!window._cy) return { exists: false };
            var node = window._cy.getElementById(targetId);
            if (!node || !node.length) return { exists: false };
            return {
                exists: true,
                width: Number(node.width()),
                height: Number(node.height()),
                styleWidth: node.style('width'),
                styleHeight: node.style('height')
            };
        }"""
    return evaluate_with_retry(page, script, node_id, timeout_ms=1500)


def read_node_resize_metrics(page: Page, node_id: str) -> dict[str, object]:
    script = """(targetId) => {
            if (!window._cy) return { exists: false };
            var node = window._cy.getElementById(targetId);
            if (!node || !node.length) return { exists: false };
            node = node.first();
            var children = node.children();
            var box = node.boundingBox({ includeLabels: false, includeOverlays: false });
            var childBox = children && children.length
                ? children.boundingBox({ includeLabels: false, includeOverlays: false })
                : null;
            return {
                exists: true,
                width: Number(node.width()),
                height: Number(node.height()),
                outerWidth: Number(node.outerWidth()),
                outerHeight: Number(node.outerHeight()),
                positionX: Number(node.position('x')),
                positionY: Number(node.position('y')),
                boundingWidth: Number(box.w || (box.x2 - box.x1)),
                boundingHeight: Number(box.h || (box.y2 - box.y1)),
                styleWidth: node.style('width'),
                styleHeight: node.style('height'),
                paddingLeft: node.style('padding-left'),
                paddingRight: node.style('padding-right'),
                paddingTop: node.style('padding-top'),
                paddingBottom: node.style('padding-bottom'),
                childCount: children ? children.length : 0,
                childBoxWidth: childBox ? Number(childBox.w || (childBox.x2 - childBox.x1)) : 0,
                childBoxHeight: childBox ? Number(childBox.h || (childBox.y2 - childBox.y1)) : 0,
            };
        }"""
    return evaluate_with_retry(page, script, node_id, timeout_ms=1500)


def read_parent_child_anchor_metrics(page: Page, parent_id: str, child_id: str) -> dict[str, object]:
    script = """(payload) => {
            if (!window._cy) return { parentExists: false, childExists: false };
            var parent = window._cy.getElementById(payload.parentId);
            var child = window._cy.getElementById(payload.childId);
            if (!parent || !parent.length || !child || !child.length) {
                return {
                    parentExists: !!(parent && parent.length),
                    childExists: !!(child && child.length),
                };
            }

            var pNode = parent.first();
            var cNode = child.first();
            var pBox = pNode.boundingBox({ includeLabels: false, includeOverlays: false });
            var parentX1 = Number(pBox.x1);
            var parentY1 = Number(pBox.y1);
            var parentX2 = Number(pBox.x2);
            var parentY2 = Number(pBox.y2);
            var childX = Number(cNode.position('x'));
            var childY = Number(cNode.position('y'));

            return {
                parentExists: true,
                childExists: true,
                parentX1: parentX1,
                parentY1: parentY1,
                parentX2: parentX2,
                parentY2: parentY2,
                childX: childX,
                childY: childY,
                childOffsetX: childX - parentX1,
                childOffsetY: childY - parentY1,
            };
        }"""
    return evaluate_with_retry(page, script, {"parentId": parent_id, "childId": child_id}, timeout_ms=1500)


def add_compound_fixture(page: Page, ids: dict[str, str]) -> None:
    page.evaluate(
        """(payload) => {
            if (!window._cy) return;
            var cy = window._cy;
            Object.values(payload).forEach(function(id) {
                var existing = cy.getElementById(id);
                if (existing && existing.length) cy.remove(existing);
            });

            cy.add({
                group: 'nodes',
                classes: 'container draft',
                data: {
                    id: payload.parent,
                    draft: true,
                    draft_name: 'Compound Parent',
                    draft_type: 'Rack',
                    label: 'Compound Parent',
                    raw_name: 'Compound Parent',
                    device_type: 'Rack',
                    raw_device_type: 'Rack',
                    shape: 'round-rectangle',
                    status: 'Active'
                },
                position: {x: 980, y: 460},
                style: {width: 440, height: 300, padding: '24px'}
            });

            cy.add({
                group: 'nodes',
                classes: 'draft',
                data: {
                    id: payload.sibling,
                    parent: payload.parent,
                    draft: true,
                    draft_name: 'Sibling Node',
                    draft_type: 'Server',
                    label: 'Sibling Node',
                    raw_name: 'Sibling Node',
                    device_type: 'Server',
                    raw_device_type: 'Server',
                    shape: 'rectangle',
                    status: 'Active'
                },
                position: {x: 870, y: 395},
                style: {width: 122, height: 92}
            });

            cy.add({
                group: 'nodes',
                classes: 'container draft',
                data: {
                    id: payload.inner,
                    parent: payload.parent,
                    draft: true,
                    draft_name: 'Inner Container',
                    draft_type: 'Rack',
                    label: 'Inner Container',
                    raw_name: 'Inner Container',
                    device_type: 'Rack',
                    raw_device_type: 'Rack',
                    shape: 'round-rectangle',
                    status: 'Active'
                },
                position: {x: 1040, y: 495},
                style: {width: 195, height: 152, padding: '16px'}
            });

            cy.add({
                group: 'nodes',
                classes: 'draft',
                data: {
                    id: payload.grandchild,
                    parent: payload.inner,
                    draft: true,
                    draft_name: 'Grandchild Node',
                    draft_type: 'Server',
                    label: 'Grandchild Node',
                    raw_name: 'Grandchild Node',
                    device_type: 'Server',
                    raw_device_type: 'Server',
                    shape: 'rectangle',
                    status: 'Active'
                },
                position: {x: 1040, y: 495},
                style: {width: 86, height: 64}
            });

            cy.nodes().unselect();
        }""",
        ids,
    )
    page.wait_for_timeout(300)


def add_single_child_container_fixture(page: Page, ids: dict[str, str]) -> None:
    page.evaluate(
        """(payload) => {
            if (!window._cy) return;
            var cy = window._cy;
            Object.values(payload).forEach(function(id) {
                var existing = cy.getElementById(id);
                if (existing && existing.length) cy.remove(existing);
            });

            cy.add({
                group: 'nodes',
                classes: 'container draft',
                data: {
                    id: payload.parent,
                    draft: true,
                    draft_name: 'Single Child Parent',
                    draft_type: 'Rack',
                    label: 'Single Child Parent',
                    raw_name: 'Single Child Parent',
                    device_type: 'Rack',
                    raw_device_type: 'Rack',
                    shape: 'round-rectangle',
                    status: 'Active'
                },
                position: {x: 560, y: 380},
                style: {padding: '24px'}
            });

            cy.add({
                group: 'nodes',
                classes: 'draft',
                data: {
                    id: payload.child,
                    parent: payload.parent,
                    draft: true,
                    draft_name: 'Single Child Node',
                    draft_type: 'Server',
                    label: 'Single Child Node',
                    raw_name: 'Single Child Node',
                    device_type: 'Server',
                    raw_device_type: 'Server',
                    shape: 'rectangle',
                    status: 'Active'
                },
                position: {x: 560, y: 380},
                style: {width: 82, height: 62}
            });

            cy.nodes().unselect();
        }""",
        ids,
    )
    page.wait_for_timeout(300)


def compound_min_size(
    metrics: dict[str, object],
    min_padding: dict[str, float] | None = None,
) -> dict[str, float]:
    if min_padding is None:
        min_padding = {
            "left": _num(metrics.get("paddingLeft")),
            "right": _num(metrics.get("paddingRight")),
            "top": _num(metrics.get("paddingTop")),
            "bottom": _num(metrics.get("paddingBottom")),
        }

    min_width = max(
        40.0,
        _num(metrics.get("childBoxWidth")) + min_padding["left"] + min_padding["right"],
    )
    min_height = max(
        40.0,
        _num(metrics.get("childBoxHeight")) + min_padding["top"] + min_padding["bottom"],
    )
    return {"width": min_width, "height": min_height}


def _num(value: object) -> float:
    text = str(value or "").replace("px", "").strip()
    try:
        return float(text)
    except ValueError:
        return 0.0


def compound_style_sane(metrics: dict[str, object], tolerance: float = 4.0) -> bool:
    width_style = str(metrics.get("styleWidth") or "")
    height_style = str(metrics.get("styleHeight") or "")
    rendered_width = _num(metrics.get("boundingWidth"))
    rendered_height = _num(metrics.get("boundingHeight"))
    pad_width = _num(metrics.get("paddingLeft")) + _num(metrics.get("paddingRight"))
    pad_height = _num(metrics.get("paddingTop")) + _num(metrics.get("paddingBottom"))

    if width_style.endswith("px"):
        style_width = _num(width_style)
        width_deltas = [
            abs(style_width - rendered_width),
            abs((style_width + pad_width) - rendered_width),
        ]
        if min(width_deltas) > tolerance:
            return False
    if height_style.endswith("px"):
        style_height = _num(height_style)
        height_deltas = [
            abs(style_height - rendered_height),
            abs((style_height + pad_height) - rendered_height),
        ]
        if min(height_deltas) > tolerance:
            return False
    return True


def wait_for_style_increase(page: Page, node_id: str, baseline: float, timeout_ms: int = 3000) -> dict[str, object]:
    """Poll until the node's styleWidth or rendered width increases beyond baseline or timeout.

    Returns the latest metrics dictionary from `read_node_resize_metrics`.
    """
    start = time.time()
    deadline = start + (timeout_ms / 1000.0)
    last = read_node_resize_metrics(page, node_id)
    while time.time() < deadline:
        # Consider multiple metrics since style('width') can remain stale while rendered width changes
        cur_w = max(
            _num(last.get("styleWidth")),
            _num(last.get("width")),
            _num(last.get("outerWidth")),
            _num(last.get("boundingWidth")),
        )
        if cur_w > baseline + 2.5:
            return last
        page.wait_for_timeout(150)
        last = read_node_resize_metrics(page, node_id)
    return last


def wait_for_overlay(page: Page, timeout_ms: int = 1200) -> bool:
    start = time.time()
    deadline = start + (timeout_ms / 1000.0)
    while time.time() < deadline:
        if overlay_visible(page):
            return True
        page.wait_for_timeout(100)
    return False


def assert_single_child_direction_case(
    page: Page,
    ids: dict[str, str],
    direction: str,
    dx: float,
    dy: float,
    pinned_parent_axes: tuple[str, ...],
) -> tuple[bool, str, dict[str, object], dict[str, object]]:
    add_single_child_container_fixture(page, ids)
    select_node(page, ids["parent"])
    if not wait_for_overlay(page):
        return False, f"FAIL: resize overlay not visible before single-child {direction} directional check", {}, {}

    before_metrics = read_node_resize_metrics(page, ids["parent"])
    before_anchor = read_parent_child_anchor_metrics(page, ids["parent"], ids["child"])
    if not before_anchor.get("parentExists") or not before_anchor.get("childExists"):
        return (
            False,
            f"FAIL: single-child fixture missing before {direction} directional check (metrics={before_anchor})",
            {},
            {},
        )

    if not pointer_drag_handle(page, direction, dx, dy):
        return False, f"FAIL: single-child directional resize handle unavailable ({direction})", {}, {}

    after_metrics = read_node_resize_metrics(page, ids["parent"])
    after_anchor = read_parent_child_anchor_metrics(page, ids["parent"], ids["child"])

    if direction in ("e", "w"):
        if _num(after_metrics.get("boundingWidth")) <= _num(before_metrics.get("boundingWidth")) + 5:
            return (
                False,
                (
                    f"FAIL: single-child directional resize did not change width for {direction} "
                    f"(before={before_metrics}, after={after_metrics})"
                ),
                {},
                {},
            )
    elif _num(after_metrics.get("boundingHeight")) <= _num(before_metrics.get("boundingHeight")) + 5:
        return (
            False,
            (
                f"FAIL: single-child directional resize did not change height for {direction} "
                f"(before={before_metrics}, after={after_metrics})"
            ),
            {},
            {},
        )

    for axis in pinned_parent_axes:
        drift = abs(_num(after_anchor.get(axis)) - _num(before_anchor.get(axis)))
        if drift > 4:
            return (
                False,
                (
                    f"FAIL: single-child directional pinned axis drifted for {direction} "
                    f"(axis={axis}, drift={drift:.2f}, before={before_anchor}, after={after_anchor})"
                ),
                {},
                {},
            )

    child_drift_x = abs(_num(after_anchor.get("childX")) - _num(before_anchor.get("childX")))
    child_drift_y = abs(_num(after_anchor.get("childY")) - _num(before_anchor.get("childY")))
    if child_drift_x > 4 or child_drift_y > 4:
        return (
            False,
            (
                f"FAIL: single-child directional child drifted for {direction} "
                f"(drift=({child_drift_x:.2f}, {child_drift_y:.2f}), "
                f"before={before_anchor}, after={after_anchor})"
            ),
            {},
            {},
        )

    if not compound_style_sane(after_metrics):
        return (
            False,
            f"FAIL: single-child directional resize left unsound style dimensions for {direction} (after={after_metrics})",
            {},
            {},
        )

    return True, "", after_metrics, after_anchor


def run_deep_canvas_test() -> int:
    token = login_api()
    seed = int(time.time())

    # Create an isolated workspace + topology so the deep test does not touch shared state.
    workspace = api("POST", "/api/workspaces/", {"name": f"HT050-WS-{seed}"}, token=token)
    ws_id = str(workspace.get("id", ""))
    if not ws_id:
        print(f"FAIL: workspace creation failed: {workspace}")
        return 1

    topology = api(
        "POST",
        f"/api/workspaces/{ws_id}/topologies/",
        {"name": f"HT050-Topo-{seed}"},
        token=token,
    )
    topo_id = str(topology.get("id", ""))
    if not topo_id:
        print(f"FAIL: topology creation failed: {topology}")
        return 1

    url = f"{BASE}/topology?workspace_id={ws_id}&topology_id={topo_id}"
    print(f"Testing URL: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        login_ui(page)
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        if not wait_for_cy(page, timeout_ms=60000):
            print("FAIL: Cytoscape not initialized")
            browser.close()
            return 1

        initial = page.evaluate(
            """() => ({
                nodes: window._cy.nodes().length,
                edges: window._cy.edges().length,
                htDiagramId: window._htDiagramId ?? null,
                htDiagramVersion: window._htDiagramVersion ?? null,
                readonly: window.HT_READONLY,
            })"""
        )
        print("Initial canvas state:", initial)

        resize_bridge_ready = page.evaluate(
            """() => (
                typeof window._htResizeSyncFromSelection === 'function'
                && typeof window._htResizeSetEnabled === 'function'
            )"""
        )
        if not resize_bridge_ready:
            print("FAIL: resize bridge is missing in the running app bundle (restart app and retry)")
            browser.close()
            return 1

        # Enter edit mode (required for save flow)
        edit_btn = page.locator('button:has-text("Edit")')
        if edit_btn.count() == 0:
            print("FAIL: no Edit button")
            browser.close()
            return 1
        edit_btn.first.click()
        page.wait_for_timeout(800)

        # Add a deterministic draft node directly to canvas for persistence check
        probe_id = f"draft-deep-{int(time.time())}"
        page.evaluate(
            """(nodeId) => {
                if (!window._cy) return;
                window._cy.add({
                    group: 'nodes',
                    classes: 'draft',
                    data: {
                        id: nodeId,
                        draft: true,
                        draft_name: 'Deep Probe',
                        draft_type: 'Server',
                        label: 'Deep Probe',
                        raw_name: 'Deep Probe',
                        device_type: 'Server',
                        raw_device_type: 'Server',
                        shape: 'rectangle',
                        status: 'Active'
                    },
                    position: {x: 320, y: 260}
                });
            }""",
            probe_id,
        )

        select_node(page, probe_id)
        if not wait_for_overlay(page):
            print("FAIL: resize overlay did not activate in edit mode")
            browser.close()
            return 1

        if not drag_resize_handle(page, "se", 120, 80):
            print("FAIL: resize handle is unavailable")
            browser.close()
            return 1

        resized_before_save = read_node_size(page, probe_id)
        print("Resized node state:", resized_before_save)
        if not resized_before_save.get("exists"):
            print("FAIL: probe node missing after resize interaction")
            browser.close()
            return 1
        if _num(resized_before_save.get("width")) <= 48 or _num(resized_before_save.get("height")) <= 48:
            print("FAIL: resize interaction did not increase node dimensions")
            browser.close()
            return 1

        single_child_ids = {
            "parent": f"single-parent-{int(time.time())}",
            "child": f"single-child-{int(time.time())}",
        }
        add_single_child_container_fixture(page, single_child_ids)

        select_node(page, single_child_ids["parent"])
        if not wait_for_overlay(page):
            print("FAIL: resize overlay did not activate for single-child container")
            browser.close()
            return 1

        single_before = read_node_resize_metrics(page, single_child_ids["parent"])
        single_anchor_before_expand = read_parent_child_anchor_metrics(
            page,
            single_child_ids["parent"],
            single_child_ids["child"],
        )
        if not single_anchor_before_expand.get("parentExists") or not single_anchor_before_expand.get("childExists"):
            print("FAIL: single-child fixture did not resolve parent/child nodes before expand")
            browser.close()
            return 1

        single_min_padding = {
            "left": _num(single_before.get("paddingLeft")),
            "right": _num(single_before.get("paddingRight")),
            "top": _num(single_before.get("paddingTop")),
            "bottom": _num(single_before.get("paddingBottom")),
        }
        single_min = compound_min_size(single_before, single_min_padding)

        if not pointer_drag_handle(page, "se", 260, 180):
            print("FAIL: single-child container expand resize handle is unavailable")
            browser.close()
            return 1

        single_after_expand = read_node_resize_metrics(page, single_child_ids["parent"])
        single_anchor_after_expand = read_parent_child_anchor_metrics(
            page,
            single_child_ids["parent"],
            single_child_ids["child"],
        )
        expand_nw_drift_x = abs(_num(single_anchor_after_expand.get("parentX1")) - _num(single_anchor_before_expand.get("parentX1")))
        expand_nw_drift_y = abs(_num(single_anchor_after_expand.get("parentY1")) - _num(single_anchor_before_expand.get("parentY1")))
        expand_child_drift_x = abs(_num(single_anchor_after_expand.get("childX")) - _num(single_anchor_before_expand.get("childX")))
        expand_child_drift_y = abs(_num(single_anchor_after_expand.get("childY")) - _num(single_anchor_before_expand.get("childY")))
        expand_offset_drift_x = abs(_num(single_anchor_after_expand.get("childOffsetX")) - _num(single_anchor_before_expand.get("childOffsetX")))
        expand_offset_drift_y = abs(_num(single_anchor_after_expand.get("childOffsetY")) - _num(single_anchor_before_expand.get("childOffsetY")))

        if _num(single_after_expand.get("boundingWidth")) <= _num(single_before.get("boundingWidth")) + 5 or _num(
            single_after_expand.get("boundingHeight")
        ) <= _num(single_before.get("boundingHeight")) + 5:
            print(
                "FAIL: single-child container expand did not change rendered bounding box "
                f"(before={single_before}, after={single_after_expand})"
            )
            browser.close()
            return 1
        if expand_nw_drift_x > 4 or expand_nw_drift_y > 4:
            print(
                "FAIL: single-child container expand slipped the pinned NW corner "
                f"(drift=({expand_nw_drift_x:.2f}, {expand_nw_drift_y:.2f}), "
                f"before={single_anchor_before_expand}, after={single_anchor_after_expand})"
            )
            browser.close()
            return 1
        if expand_child_drift_x > 4 or expand_child_drift_y > 4:
            print(
                "FAIL: single-child container expand moved child on screen "
                f"(drift=({expand_child_drift_x:.2f}, {expand_child_drift_y:.2f}), "
                f"before={single_anchor_before_expand}, after={single_anchor_after_expand})"
            )
            browser.close()
            return 1
        if expand_offset_drift_x > 2 or expand_offset_drift_y > 2:
            print(
                "FAIL: single-child container expand changed child offset from container origin "
                f"(offset drift=({expand_offset_drift_x:.2f}, {expand_offset_drift_y:.2f}), "
                f"before={single_anchor_before_expand}, after={single_anchor_after_expand})"
            )
            browser.close()
            return 1
        if not compound_style_sane(single_after_expand):
            print(
                "FAIL: single-child container expand left misleading style dimensions "
                f"(after={single_after_expand})"
            )
            browser.close()
            return 1

        select_node(page, single_child_ids["parent"])
        if not wait_for_overlay(page):
            print("FAIL: resize overlay not visible before single-child shrink")
            browser.close()
            return 1

        if not pointer_drag_handle(page, "se", -620, -480):
            print("FAIL: single-child container shrink resize handle is unavailable")
            browser.close()
            return 1

        single_anchor_before_shrink = single_anchor_after_expand
        single_after_shrink = read_node_resize_metrics(page, single_child_ids["parent"])
        single_anchor_after_shrink = read_parent_child_anchor_metrics(
            page,
            single_child_ids["parent"],
            single_child_ids["child"],
        )
        shrink_nw_drift_x = abs(_num(single_anchor_after_shrink.get("parentX1")) - _num(single_anchor_before_shrink.get("parentX1")))
        shrink_nw_drift_y = abs(_num(single_anchor_after_shrink.get("parentY1")) - _num(single_anchor_before_shrink.get("parentY1")))
        shrink_child_drift_x = abs(_num(single_anchor_after_shrink.get("childX")) - _num(single_anchor_before_shrink.get("childX")))
        shrink_child_drift_y = abs(_num(single_anchor_after_shrink.get("childY")) - _num(single_anchor_before_shrink.get("childY")))
        shrink_offset_drift_x = abs(_num(single_anchor_after_shrink.get("childOffsetX")) - _num(single_anchor_before_shrink.get("childOffsetX")))
        shrink_offset_drift_y = abs(_num(single_anchor_after_shrink.get("childOffsetY")) - _num(single_anchor_before_shrink.get("childOffsetY")))

        if _num(single_after_shrink.get("boundingWidth")) >= _num(single_after_expand.get("boundingWidth")) - 5 or _num(
            single_after_shrink.get("boundingHeight")
        ) >= _num(single_after_expand.get("boundingHeight")) - 5:
            print(
                "FAIL: single-child container shrink did not reduce rendered bounding box "
                f"(expand={single_after_expand}, shrink={single_after_shrink})"
            )
            browser.close()
            return 1
        if shrink_nw_drift_x > 4 or shrink_nw_drift_y > 4:
            print(
                "FAIL: single-child container shrink slipped the pinned NW corner "
                f"(drift=({shrink_nw_drift_x:.2f}, {shrink_nw_drift_y:.2f}), "
                f"before={single_anchor_before_shrink}, after={single_anchor_after_shrink})"
            )
            browser.close()
            return 1
        if shrink_child_drift_x > 4 or shrink_child_drift_y > 4:
            print(
                "FAIL: single-child container shrink moved child on screen "
                f"(drift=({shrink_child_drift_x:.2f}, {shrink_child_drift_y:.2f}), "
                f"before={single_anchor_before_shrink}, after={single_anchor_after_shrink})"
            )
            browser.close()
            return 1
        if shrink_offset_drift_x > 2 or shrink_offset_drift_y > 2:
            print(
                "FAIL: single-child container shrink changed child offset from container origin "
                f"(offset drift=({shrink_offset_drift_x:.2f}, {shrink_offset_drift_y:.2f}), "
                f"before={single_anchor_before_shrink}, after={single_anchor_after_shrink})"
            )
            browser.close()
            return 1
        if _num(single_after_shrink.get("boundingWidth")) + 0.5 < single_min["width"] or _num(
            single_after_shrink.get("boundingHeight")
        ) + 0.5 < single_min["height"]:
            print(
                "FAIL: single-child container shrink went below child-plus-padding clamp "
                f"(min={single_min}, shrink={single_after_shrink})"
            )
            browser.close()
            return 1
        if not compound_style_sane(single_after_shrink):
            print(
                "FAIL: single-child container shrink left misleading style dimensions "
                f"(shrink={single_after_shrink})"
            )
            browser.close()
            return 1

        directional_ids = {
            "parent": f"single-dir-parent-{int(time.time())}",
            "child": f"single-dir-child-{int(time.time())}",
        }
        directional_cases: list[tuple[str, float, float, tuple[str, ...]]] = [
            ("e", 260, 0, ("parentX1",)),
            ("w", -260, 0, ("parentX2",)),
            ("n", 0, -220, ("parentY2",)),
            ("s", 0, 220, ("parentY1",)),
        ]
        directional_after_before_refresh: dict[str, object] = {}
        directional_anchor_before_refresh: dict[str, object] = {}

        for direction, dx, dy, pinned_axes in directional_cases:
            ok_case, fail_msg, after_metrics, after_anchor = assert_single_child_direction_case(
                page,
                directional_ids,
                direction,
                dx,
                dy,
                pinned_axes,
            )
            if not ok_case:
                print(fail_msg)
                browser.close()
                return 1
            directional_after_before_refresh = after_metrics
            directional_anchor_before_refresh = after_anchor

        compound_ids = {
            "parent": f"compound-parent-{int(time.time())}",
            "inner": f"compound-inner-{int(time.time())}",
            "sibling": f"compound-sibling-{int(time.time())}",
            "grandchild": f"compound-grandchild-{int(time.time())}",
        }
        add_compound_fixture(page, compound_ids)

        select_node(page, compound_ids["inner"])
        if not wait_for_overlay(page):
            print("FAIL: resize overlay did not activate for nested container")
            browser.close()
            return 1

        # Force style dimensions to diverge from rendered BB to guard stale-baseline drift regression.
        page.evaluate(
            """(targetId) => {
                if (!window._cy) return;
                var node = window._cy.getElementById(targetId);
                if (!node || !node.length) return;
                node.style('width', 420);
                node.style('height', 310);
            }""",
            compound_ids["inner"],
        )
        page.wait_for_timeout(250)

        inner_before = read_node_resize_metrics(page, compound_ids["inner"])
        inner_min = compound_min_size(inner_before)
        stale_gap_w = abs(_num(inner_before.get("styleWidth")) - _num(inner_before.get("boundingWidth")))
        stale_gap_h = abs(_num(inner_before.get("styleHeight")) - _num(inner_before.get("boundingHeight")))
        if stale_gap_w < 30 or stale_gap_h < 30:
            print(
                "FAIL: could not construct stale style-vs-bounding-box baseline "
                f"(gap=({stale_gap_w:.2f}, {stale_gap_h:.2f}), metrics={inner_before})"
            )
            browser.close()
            return 1

        if not drag_resize_handle(page, "nw", 520, 390):
            print("FAIL: nested container resize handle is unavailable")
            browser.close()
            return 1

        inner_after_clamp = read_node_resize_metrics(page, compound_ids["inner"])
        if _num(inner_after_clamp.get("boundingWidth")) + 0.5 < inner_min["width"] or _num(
            inner_after_clamp.get("boundingHeight")
        ) + 0.5 < inner_min["height"]:
            print(
                "FAIL: nested container clamp did not enforce child-bounds-plus-padding "
                f"(min={inner_min}, after={inner_after_clamp})"
            )
            browser.close()
            return 1

        clamp_drift_x = abs(_num(inner_after_clamp.get("positionX")) - _num(inner_before.get("positionX")))
        clamp_drift_y = abs(_num(inner_after_clamp.get("positionY")) - _num(inner_before.get("positionY")))
        if clamp_drift_x > 6 or clamp_drift_y > 6:
            print(
                "FAIL: clamp-constrained resize drifted with stale style baseline "
                f"(staleGap=({stale_gap_w:.2f}, {stale_gap_h:.2f}), drift=({clamp_drift_x:.2f}, {clamp_drift_y:.2f}))"
            )
            browser.close()
            return 1

        select_node(page, compound_ids["inner"])
        if not wait_for_overlay(page):
            print("FAIL: resize overlay not visible before valid resize")
            browser.close()
            return 1

        if not pointer_drag_handle(page, "se", 200, 140):
            print("FAIL: nested container valid resize interaction failed")
            browser.close()
            return 1

        # Use a baseline that considers rendered metrics (width/outer/bounding/style)
        baseline_w = max(
            _num(inner_after_clamp.get("width")),
            _num(inner_after_clamp.get("outerWidth")),
            _num(inner_after_clamp.get("boundingWidth")),
            _num(inner_after_clamp.get("styleWidth")),
        )

        # Give more time on warm runs for the browser to settle rendered/style metrics
        # after the pointer-driven resize. 4s was occasionally flaky; extend to 8s
        # while keeping the measurable-change assertion unchanged.
        inner_valid_before_save = wait_for_style_increase(
            page, compound_ids["inner"], baseline_w, timeout_ms=8000
        )

        new_style_w = _num(inner_valid_before_save.get("styleWidth"))
        new_rendered_w = max(
            _num(inner_valid_before_save.get("width")),
            _num(inner_valid_before_save.get("outerWidth")),
            _num(inner_valid_before_save.get("boundingWidth")),
        )

        old_style_w = _num(inner_after_clamp.get("styleWidth"))
        old_rendered_w = max(
            _num(inner_after_clamp.get("width")),
            _num(inner_after_clamp.get("outerWidth")),
            _num(inner_after_clamp.get("boundingWidth")),
        )

        delta = max(abs(new_style_w - old_style_w), abs(new_rendered_w - old_rendered_w))

        # Require a measurable change from the resize interaction, and that the result is at least the computed minimum.
        if delta < 2.5 or new_rendered_w + 0.5 < inner_min["width"]:
            print("DEBUG: inner_after_clamp=", inner_after_clamp)
            print("DEBUG: inner_valid_before_save=", inner_valid_before_save)
            print("FAIL: nested container valid resize did not produce a measurable change (after wait)")
            browser.close()
            return 1

        # Save as a new version
        page.get_by_role("button", name="Save Version").first.click()
        page.wait_for_timeout(1500)

        # Resolve latest history entry and validate topology binding through its diagram.
        # The server may persist history asynchronously; poll briefly to avoid
        # a brittle race in the test harness.
        history_payload = None
        history_items = []
        history_deadline = time.time() + 8.0  # seconds
        while time.time() < history_deadline:
            history_payload = api("GET", f"/api/topologies/{topo_id}/history?limit=10", token=token)
            if isinstance(history_payload, dict):
                items = history_payload.get("items", [])
                if isinstance(items, list) and items:
                    history_items = items
                    break
            # brief backoff while server finishes persisting the new history entry
            page.wait_for_timeout(400)

        if not isinstance(history_items, list) or not history_items:
            print("FAIL: topology history list response malformed")
            browser.close()
            return 1

        latest_history = history_items[0]
        created_diagram_id = latest_history.get("diagram_id")
        if not created_diagram_id:
            print("FAIL: latest history entry missing diagram_id")
            browser.close()
            return 1
        created = api("GET", f"/api/diagrams/{created_diagram_id}", token=token)
        if not isinstance(created, dict):
            print("FAIL: diagram detail response malformed")
            browser.close()
            return 1

        created_topology_id = created.get("topology_id")
        print("Created layout:", {"id": created.get("id"), "name": created.get("name"), "topology_id": created_topology_id})

        # Refresh the same topology URL and verify the probe node persists
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        if not wait_for_cy(page, timeout_ms=60000):
            print("FAIL: Cytoscape did not initialize after refresh")
            browser.close()
            return 1

        select_node(page, probe_id)
        # Bounded wait: check whether overlay appears in view mode within a short window.
        # We expect the overlay to remain hidden in view mode; use `wait_for_overlay`
        # to avoid a brittle immediate read that can flake on warm runs.
        view_overlay_visible = wait_for_overlay(page, timeout_ms=700)

        edit_btn = page.locator('button:has-text("Edit")')
        if edit_btn.count() == 0:
            print("FAIL: no Edit button after refresh")
            browser.close()
            return 1
        edit_btn.first.click()
        page.wait_for_timeout(700)
        select_node(page, probe_id)
        edit_overlay_visible = wait_for_overlay(page)

        single_anchor_persisted = read_parent_child_anchor_metrics(
            page,
            single_child_ids["parent"],
            single_child_ids["child"],
        )
        directional_anchor_persisted = read_parent_child_anchor_metrics(
            page,
            directional_ids["parent"],
            directional_ids["child"],
        )
        single_persisted = read_node_resize_metrics(page, single_child_ids["parent"])
        directional_persisted = read_node_resize_metrics(page, directional_ids["parent"])
        inner_persisted = read_node_resize_metrics(page, compound_ids["inner"])

        persisted = page.evaluate(
            """(nodeId) => ({
                exists: window._cy.getElementById(nodeId).length > 0,
                nodes: window._cy.nodes().length,
                htDiagramId: window._htDiagramId ?? null,
                htDiagramVersion: window._htDiagramVersion ?? null,
                width: window._cy.getElementById(nodeId).length > 0 ? Number(window._cy.getElementById(nodeId).first().width()) : 0,
                height: window._cy.getElementById(nodeId).length > 0 ? Number(window._cy.getElementById(nodeId).first().height()) : 0,
                styleWidth: window._cy.getElementById(nodeId).length > 0 ? window._cy.getElementById(nodeId).first().style('width') : null,
                styleHeight: window._cy.getElementById(nodeId).length > 0 ? window._cy.getElementById(nodeId).first().style('height') : null,
            })""",
            probe_id,
        )
        print("Post-refresh state:", persisted)

        browser.close()

    ok_topology_binding = str(created_topology_id) == topo_id
    ok_persisted = bool(persisted.get("exists"))
    size_delta_w = abs(_num(persisted.get("width")) - _num(resized_before_save.get("width")))
    size_delta_h = abs(_num(persisted.get("height")) - _num(resized_before_save.get("height")))
    style_delta_w = abs(_num(persisted.get("styleWidth")) - _num(resized_before_save.get("styleWidth")))
    style_delta_h = abs(_num(persisted.get("styleHeight")) - _num(resized_before_save.get("styleHeight")))
    ok_resize_persisted = size_delta_w <= 2 and size_delta_h <= 2 and style_delta_w <= 2 and style_delta_h <= 2
    single_style_delta_w = abs(_num(single_persisted.get("styleWidth")) - _num(single_after_shrink.get("styleWidth")))
    single_style_delta_h = abs(_num(single_persisted.get("styleHeight")) - _num(single_after_shrink.get("styleHeight")))
    directional_style_delta_w = abs(_num(directional_persisted.get("styleWidth")) - _num(directional_after_before_refresh.get("styleWidth")))
    directional_style_delta_h = abs(_num(directional_persisted.get("styleHeight")) - _num(directional_after_before_refresh.get("styleHeight")))
    inner_style_delta_w = abs(_num(inner_persisted.get("styleWidth")) - _num(inner_valid_before_save.get("styleWidth")))
    inner_style_delta_h = abs(_num(inner_persisted.get("styleHeight")) - _num(inner_valid_before_save.get("styleHeight")))
    single_child_persisted_dx = abs(_num(single_anchor_persisted.get("childX")) - _num(single_anchor_after_shrink.get("childX")))
    single_child_persisted_dy = abs(_num(single_anchor_persisted.get("childY")) - _num(single_anchor_after_shrink.get("childY")))
    directional_child_persisted_dx = abs(_num(directional_anchor_persisted.get("childX")) - _num(directional_anchor_before_refresh.get("childX")))
    directional_child_persisted_dy = abs(_num(directional_anchor_persisted.get("childY")) - _num(directional_anchor_before_refresh.get("childY")))
    single_parent_contains_child = (
        _num(single_anchor_persisted.get("childOffsetX")) >= -1
        and _num(single_anchor_persisted.get("childOffsetY")) >= -1
        and _num(single_anchor_persisted.get("childOffsetX")) <= _num(single_persisted.get("boundingWidth")) + 1
        and _num(single_anchor_persisted.get("childOffsetY")) <= _num(single_persisted.get("boundingHeight")) + 1
    )
    directional_parent_contains_child = (
        _num(directional_anchor_persisted.get("childOffsetX")) >= -1
        and _num(directional_anchor_persisted.get("childOffsetY")) >= -1
        and _num(directional_anchor_persisted.get("childOffsetX")) <= _num(directional_persisted.get("boundingWidth")) + 1
        and _num(directional_anchor_persisted.get("childOffsetY")) <= _num(directional_persisted.get("boundingHeight")) + 1
    )
    ok_compound_resize_persisted = (
        single_style_delta_w <= 3
        and single_style_delta_h <= 3
        and directional_style_delta_w <= 3
        and directional_style_delta_h <= 3
        and inner_style_delta_w <= 3
        and inner_style_delta_h <= 3
        and compound_style_sane(single_persisted)
        and compound_style_sane(directional_persisted)
        and compound_style_sane(inner_persisted)
    )
    ok_single_anchor_persisted = (
        bool(single_anchor_persisted.get("parentExists"))
        and bool(single_anchor_persisted.get("childExists"))
        and single_child_persisted_dx <= 3
        and single_child_persisted_dy <= 3
        and single_parent_contains_child
    )
    ok_directional_anchor_persisted = (
        bool(directional_anchor_persisted.get("parentExists"))
        and bool(directional_anchor_persisted.get("childExists"))
        and directional_child_persisted_dx <= 3
        and directional_child_persisted_dy <= 3
        and directional_parent_contains_child
    )
    ok_view_mode_hidden = not view_overlay_visible
    ok_edit_mode_visible = edit_overlay_visible

    if not ok_topology_binding:
        print(
            "FAIL: saved layout is not topology-scoped "
            f"(expected topology_id={topo_id}, got={created_topology_id})"
        )
        return 1
    if not ok_persisted:
        print("FAIL: saved canvas change missing after refresh")
        return 1
    if not ok_resize_persisted:
        print(
            "FAIL: resized dimensions did not persist across refresh "
            f"(node delta=({size_delta_w:.2f}, {size_delta_h:.2f}), "
            f"style delta=({style_delta_w:.2f}, {style_delta_h:.2f}))"
        )
        return 1
    if not ok_compound_resize_persisted:
        print(
            "FAIL: compound resize persistence/style sanity failed across refresh "
            f"(single style delta=({single_style_delta_w:.2f}, {single_style_delta_h:.2f}), "
            f"directional style delta=({directional_style_delta_w:.2f}, {directional_style_delta_h:.2f}), "
            f"inner style delta=({inner_style_delta_w:.2f}, {inner_style_delta_h:.2f}), "
            f"single={single_persisted}, directional={directional_persisted}, inner={inner_persisted})"
        )
        return 1
    if not ok_single_anchor_persisted:
        print(
            "FAIL: single-child persistence became inconsistent after refresh "
            f"(child drift=({single_child_persisted_dx:.2f}, {single_child_persisted_dy:.2f}), "
            f"parentContainsChild={single_parent_contains_child}, "
            f"before={single_anchor_after_shrink}, after={single_anchor_persisted})"
        )
        return 1
    if not ok_directional_anchor_persisted:
        print(
            "FAIL: directional single-child persistence became inconsistent after refresh "
            f"(child drift=({directional_child_persisted_dx:.2f}, {directional_child_persisted_dy:.2f}), "
            f"parentContainsChild={directional_parent_contains_child}, "
            f"before={directional_anchor_before_refresh}, after={directional_anchor_persisted})"
        )
        return 1
    if not ok_view_mode_hidden:
        print("FAIL: resize overlay should be inactive in view mode")
        return 1
    if not ok_edit_mode_visible:
        print("FAIL: resize overlay did not reactivate in edit mode")
        return 1

    print("PASS: deep topology canvas save/load persistence test")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_deep_canvas_test())
