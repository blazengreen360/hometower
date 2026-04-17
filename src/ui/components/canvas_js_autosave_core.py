"""Core autosave helpers for the topology canvas JS bundle."""

CANVAS_AUTOSAVE_CORE_JS = """
(function() {
    var HT_AUTOSAVE_DELAY_MS = 800;
    var HT_AUTOSAVE_RETRY_DELAYS_MS = [1000, 2000, 4000];
    var HT_AUTOSAVE_MAX_KEEPALIVE_BYTES = 65536;
    var HT_AUTOSAVE_CONFLICT_MESSAGE = 'Your personal draft was modified elsewhere \\u2014 reload to sync';
    var HT_AUTOSAVE_FAILURE_MESSAGE = 'Autosave failed. Your changes may not be saved.';
    var HT_AUTOSAVE_UNLOAD_MESSAGE = 'Save in progress \\u2014 are you sure you want to leave?';
    function _clearAutosaveTimer() {
        if (!window._htAutosaveTimer) return;
        clearTimeout(window._htAutosaveTimer);
        window._htAutosaveTimer = null;
    }
    function _clearAutosaveRetryTimer() {
        if (!window._htAutosaveRetryTimer) return;
        clearTimeout(window._htAutosaveRetryTimer);
        window._htAutosaveRetryTimer = null;
    }
    function _dismissNotify(handle) {
        if (!handle) return;
        if (typeof handle === 'function') {
            handle();
            return;
        }
        if (typeof handle.dismiss === 'function') {
            handle.dismiss();
        }
    }
    function _dismissAutosaveFailureNotice() {
        _dismissNotify(window._htAutosaveFailureHandle);
        window._htAutosaveFailureHandle = null;
        window._htAutosaveFailureShown = false;
    }

    function _canAutosave() {
        return !window.HT_READONLY
            && !window._htAutosaveSuspended
            && !!window._htTopologyId;
    }

    function _getAutosaveRequest() {
        if (!_canAutosave()) return null;
        var canvasJson = window.getCanvasJson();
        if (!canvasJson) return null;
        var bodyText = JSON.stringify({
            cytoscape_json: canvasJson,
            base_version: window._htDraftVersion != null ? window._htDraftVersion : null
        });
        window._htAutosaveLastBodySize = bodyText.length;
        return { bodyText: bodyText };
    }

    function _finishAutosave(triggerPendingFlush) {
        window._htAutosaveInFlight = false;
        window._htAutosaveRequestInFlight = false;
        _clearAutosaveRetryTimer();
        if (!triggerPendingFlush || window._htAutosaveSuspended) return;
        if (window._htAutosavePending) {
            window._htAutosavePending = false;
            window._htAutosaveDirty = true;
            window._htFlushAutosave();
        }
    }

    function _showAutosaveConflictNotice() {
        _clearAutosaveTimer();
        _clearAutosaveRetryTimer();
        window._htAutosavePending = false;
        window._htAutosaveSuspended = true;
        window._htAutosaveDirty = true;
        document.dispatchEvent(new CustomEvent('ht:autosave-conflict'));
        if (window._htAutosaveConflictShown) return;
        window._htAutosaveConflictShown = true;
        window._htNotify(HT_AUTOSAVE_CONFLICT_MESSAGE, 'warning', {
            position: 'top',
            timeout: 0,
            closeBtn: false,
            multiLine: true,
            group: 'ht-autosave-conflict',
            actions: [{
                label: 'Reload',
                color: 'white',
                textColor: 'black',
                noCaps: true,
                classes: 'full-width justify-center',
                handler: function() {
                    window.location.reload();
                }
            }]
        });
    }

    function _showAutosaveFailureNotice() {
        if (window._htAutosaveFailureShown) return;
        window._htAutosaveFailureShown = true;
        window._htAutosaveFailureHandle = window._htNotify(
            HT_AUTOSAVE_FAILURE_MESSAGE,
            'warning',
            {
                position: 'bottom-right',
                timeout: 8000,
                closeBtn: true,
                multiLine: true,
                group: 'ht-autosave-failed',
                actions: [{
                    label: 'Retry',
                    color: 'white',
                    textColor: 'black',
                    noCaps: true,
                    handler: function() {
                        _dismissAutosaveFailureNotice();
                        window.scheduleAutosave(0);
                    }
                }]
            }
        );
    }

    function _scheduleAutosaveRetry(attemptIndex) {
        var delayMs = HT_AUTOSAVE_RETRY_DELAYS_MS[attemptIndex];
        window._htAutosaveRequestInFlight = false;
        _clearAutosaveRetryTimer();
        window._htAutosaveRetryTimer = window.setTimeout(function() {
            window._htAutosaveRetryTimer = null;
            _sendAutosave(attemptIndex + 1);
        }, delayMs);
    }

    function _handleAutosaveFailure(attemptIndex, retryable) {
        window._htAutosaveRequestInFlight = false;
        if (retryable && attemptIndex < HT_AUTOSAVE_RETRY_DELAYS_MS.length) {
            _scheduleAutosaveRetry(attemptIndex);
            return;
        }
        window._htAutosavePending = false;
        window._htAutosaveDirty = true;
        _showAutosaveFailureNotice();
        _finishAutosave(false);
    }
"""