"""Runtime helpers for topology shell resize synchronization."""

import inspect

from nicegui import ui

_TOPOLOGY_LAYOUT_RUNTIME_JS = """
(function() {
    if (window._htTopologyLayoutRuntimeLoaded) return;
    window._htTopologyLayoutRuntimeLoaded = true;

    var state = {
        bound: false,
        observer: null,
        raf: null,
        retry: null,
        trailing: null,
        host: null,
    };

    function _syncNow() {
        var stage = document.getElementById('ht-topology-canvas-stage');
        if (!stage || !window._cy) return false;
        var rect = stage.getBoundingClientRect();
        if (rect.width < 8 || rect.height < 8) return false;
        window._cy.resize();
        if (window.htRefreshNetworkOverlay) window.htRefreshNetworkOverlay();
        if (window._htResizeSyncFromSelection) window._htResizeSyncFromSelection();
        return true;
    }

    function _clearTimer(name) {
        if (state[name] === null) return;
        window.clearTimeout(state[name]);
        state[name] = null;
    }

    function _scheduleRetry() {
        _clearTimer('retry');
        state.retry = window.setTimeout(function() {
            state.retry = null;
            _schedule();
        }, 140);
    }

    function _runSync() {
        state.raf = null;
        if (!_syncNow()) {
            _scheduleRetry();
            return;
        }
        _clearTimer('trailing');
        state.trailing = window.setTimeout(function() {
            state.trailing = null;
            _syncNow();
        }, 240);
    }

    function _schedule() {
        if (state.raf !== null) return;
        state.raf = window.requestAnimationFrame(_runSync);
    }

    function _handleTransitionEnd() {
        _schedule();
    }

    function _teardown() {
        if (state.observer) {
            state.observer.disconnect();
            state.observer = null;
        }
        if (state.host) {
            state.host.removeEventListener('transitionend', _handleTransitionEnd, true);
            state.host = null;
        }
        window.removeEventListener('resize', _schedule);
        window.removeEventListener('ht:topology-layout-sync', _schedule);
        if (state.raf !== null) {
            window.cancelAnimationFrame(state.raf);
            state.raf = null;
        }
        _clearTimer('retry');
        _clearTimer('trailing');
        state.bound = false;
    }

    function _bind() {
        if (state.bound) return true;
        var stage = document.getElementById('ht-topology-canvas-stage');
        var host = document.getElementById('ht-topology-shell');
        if (!stage || !host) return false;
        state.host = host;
        if (typeof ResizeObserver === 'function') {
            state.observer = new ResizeObserver(function() {
                _schedule();
            });
            state.observer.observe(stage);
        }
        host.addEventListener('transitionend', _handleTransitionEnd, true);
        window.addEventListener('resize', _schedule);
        window.addEventListener('ht:topology-layout-sync', _schedule);
        document.addEventListener('visibilitychange', function() {
            if (!document.hidden) _schedule();
        });
        window.addEventListener('pagehide', _teardown, { once: true });
        state.bound = true;
        return true;
    }

    function _ensureBound(attempt) {
        var currentAttempt = attempt || 0;
        if (_bind()) {
            _schedule();
            return;
        }
        if (currentAttempt >= 40) return;
        window.setTimeout(function() {
            _ensureBound(currentAttempt + 1);
        }, 100);
    }

    window.htInitTopologyLayoutRuntime = function() {
        _ensureBound(0);
    };

    window.htTopologyShellSync = function() {
        _ensureBound(0);
    };
})();
"""


def inject_topology_layout_runtime() -> None:
    """Inject the client runtime that keeps Cytoscape in sync with shell changes."""
    ui.add_body_html(f"<script>{_TOPOLOGY_LAYOUT_RUNTIME_JS}</script>")


def arm_topology_layout_runtime() -> None:
    """Start the topology layout runtime after the shell is rendered."""
    _run_javascript_fire_and_forget(
        "if(window.htInitTopologyLayoutRuntime) window.htInitTopologyLayoutRuntime()"
    )


def trigger_topology_layout_sync() -> None:
    """Request a Cytoscape resize pass after shell visibility or width changes."""
    _run_javascript_fire_and_forget(
        "if(window.htTopologyShellSync) window.htTopologyShellSync()"
    )


def _run_javascript_fire_and_forget(script: str) -> None:
    """Fire client-side JS without leaking coroutine warnings in tests."""
    result = ui.run_javascript(script)
    if inspect.iscoroutine(result):
        result.close()
