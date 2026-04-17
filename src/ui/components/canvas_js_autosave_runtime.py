"""Request and unload autosave helpers for the topology canvas JS bundle."""

CANVAS_AUTOSAVE_RUNTIME_JS = """

    function _dispatchAutosaveRequest(request, useKeepalive) {
        return fetch('/api/topologies/' + window._htTopologyId + '/personal-draft', {
            method: 'PUT',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: request.bodyText,
            keepalive: !!useKeepalive
        });
    }

    function _sendUnloadAutosave(request) {
        _dispatchAutosaveRequest(request, true);
    }

    function _confirmAutosaveUnload(event) { event.preventDefault(); event.returnValue = HT_AUTOSAVE_UNLOAD_MESSAGE; return HT_AUTOSAVE_UNLOAD_MESSAGE; }

    function _sendAutosave(attemptIndex) {
        var request = _getAutosaveRequest();
        if (!request) {
            _finishAutosave(false);
            return;
        }
        window._htAutosaveRequestInFlight = true;
        _dispatchAutosaveRequest(request, false).then(function(r) {
            if (r.ok) return r.json();
            if (r.status === 409) {
                _showAutosaveConflictNotice();
                _finishAutosave(false);
                return null;
            }
            _handleAutosaveFailure(
                attemptIndex,
                r.status >= 500 || r.status === 429
            );
            return null;
        })
        .then(function(data) {
            if (!data) return;
            if (data.version != null) {
                window._htDraftVersion = data.version;
            }
            if (Object.prototype.hasOwnProperty.call(data, 'has_unsaved_changes')) {
                if (window._htSetDraftStatus) {
                    window._htSetDraftStatus(!!data.has_unsaved_changes);
                } else {
                    window._htHasUnsavedChanges = !!data.has_unsaved_changes;
                }
            } else if (window._htSetDraftStatus) {
                window._htSetDraftStatus(true);
            } else {
                window._htHasUnsavedChanges = true;
            }
            window._htAutosaveDirty = false;
            _dismissAutosaveFailureNotice();
            _finishAutosave(true);
        })
        .catch(function() {
            _handleAutosaveFailure(attemptIndex, true);
        });
    }
    window.scheduleAutosave = function(delayMs) {
        if (!_canAutosave() || !window._htFlushAutosave) {
            return function() {};
        }
        window._htAutosaveDirty = true;
        if (window._htAutosaveInFlight) {
            window._htAutosavePending = true;
            return function() {};
        }
        _clearAutosaveTimer();
        var timeoutMs = typeof delayMs === 'number' ? delayMs : HT_AUTOSAVE_DELAY_MS;
        var timerId = window.setTimeout(function() {
            window._htAutosaveTimer = null;
            window._htFlushAutosave();
        }, timeoutMs);
        window._htAutosaveTimer = timerId;
        return function() {
            if (window._htAutosaveTimer !== timerId) return;
            _clearAutosaveTimer();
        };
    };

    window.cancelAutosave = function() {
        _clearAutosaveTimer();
    };

    window._htFlushAutosave = function() {
        _clearAutosaveTimer();
        if (window.HT_READONLY) return;
        if (!_canAutosave()) return;
        window._htAutosaveDirty = true;
        if (window._htAutosaveInFlight) {
            window._htAutosavePending = true;
            return;
        }
        window._htAutosaveInFlight = true;
        _sendAutosave(0);
    };

    window.addEventListener('beforeunload', function(event) {
        if (window._htLeaveGuardBypassOnce) return;
        if (!_canAutosave()) return;
        if (!window._htAutosaveDirty
            && !window._htAutosaveTimer
            && !window._htAutosaveInFlight
            && !window._htAutosavePending) {
            return;
        }
        var request = _getAutosaveRequest();
        if (!request) return;
        if (request.bodyText.length > HT_AUTOSAVE_MAX_KEEPALIVE_BYTES) {
            return _confirmAutosaveUnload(event);
        }
        if (window._htAutosaveRequestInFlight) {
            return _confirmAutosaveUnload(event);
        }
        _sendUnloadAutosave(request);
    });
})();
"""