"""Draft-specific event handlers extracted from canvas_events.py (HT-051).

Concatenated into the _htInitEventHandlers IIFE — shares its scope
(cy, _escapeHtml, _notify, deviceShapes are all in closure).
"""

CANVAS_DRAFT_EVENTS_JS: str = """
        document.addEventListener('ht:node-remove-from-view', function(evt) {
            if (window.HT_READONLY) return;
            var d = evt.detail;
            if (!window._cy) return;
            if (window._htIsDraft && window._htIsDraft(d.id)) return;

            var deviceName = (d.data && (d.data.raw_name || d.data.label)) || d.id;
            if (window.Quasar && window.Quasar.Dialog && window.Quasar.Dialog.create) {
                window.Quasar.Dialog.create({
                    title: 'Remove from View',
                    message: "Remove '" + _escapeHtml(deviceName) + "' from this View? The device stays in your inventory.",
                    ok: { label: 'Remove', color: 'warning' },
                    cancel: { label: 'Cancel', flat: true, color: 'grey-6' },
                    persistent: true,
                }).onOk(function() {
                    var el = window._cy.getElementById(d.id);
                    if (!el.length) return;
                    if (window._htCommitLocalRemoveFromView) {
                        window._htCommitLocalRemoveFromView(el);
                        return;
                    }
                    var connected = el.connectedEdges();
                    connected.remove();
                    el.remove();
                    if (window.scheduleAutosave) window.scheduleAutosave(800);
                    document.dispatchEvent(new CustomEvent('ht:stencil-refresh'));
                    _notify('Device removed from View.', 'info');
                });
            } else if (window.confirm("Remove '" + deviceName + "' from this View? The device stays in your inventory.")) {
                var el = window._cy.getElementById(d.id);
                if (!el.length) return;
                if (window._htCommitLocalRemoveFromView) {
                    window._htCommitLocalRemoveFromView(el);
                    return;
                }
                var toRemove = el.connectedEdges();
                toRemove.remove();
                el.remove();
                if (window.scheduleAutosave) window.scheduleAutosave(800);
                document.dispatchEvent(new CustomEvent('ht:stencil-refresh'));
            }
        });

        document.addEventListener('ht:node-publish', function(evt) {
            if (window.HT_READONLY) return;
            var d = evt.detail;
            if (!d || !d.id) return;
            if (window._htPublishDraft) window._htPublishDraft(d.id);
        });
"""
