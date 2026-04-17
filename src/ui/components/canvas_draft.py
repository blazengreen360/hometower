"""Draft device element helpers for the Cytoscape.js canvas.

Hides the draft element schema (ID convention, data fields, CSS class)
so that if the draft data shape changes, only this file is touched.
"""

CANVAS_DRAFT_JS: str = """
(function() {
    // Shared helpers — promoted to window scope for cross-module access
    window._htEscapeHtml = function(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    };

    window._htNotify = function(message, color, opts) {
        var options = opts || {};
        if (window.Quasar && window.Quasar.Notify) {
            var notifyConfig = {
                message: message,
                color: color || options.color || 'info',
                position: options.position || 'top-right',
                timeout: Object.prototype.hasOwnProperty.call(options, 'timeout')
                    ? options.timeout
                    : 1800,
                closeBtn: Object.prototype.hasOwnProperty.call(options, 'closeBtn')
                    ? options.closeBtn
                    : true,
                multiLine: !!options.multiLine,
                group: options.group || false,
            };
            if (Array.isArray(options.actions) && options.actions.length > 0) {
                notifyConfig.actions = options.actions;
            }
            return window.Quasar.Notify.create(notifyConfig);
        }
        console.info(message);
        return null;
    };

    window._htShowGraphCorruption = function() {
        window._htNotify(
            'Graph may be corrupted. Please reload the page to restore from last saved state.',
            'negative',
            {
                position: 'top',
                timeout: 0,
                closeBtn: false,
                multiLine: true,
                group: 'ht-graph-corruption',
                actions: [{
                    label: 'Reload',
                    color: 'white',
                    handler: function() { window.location.reload(); }
                }]
            }
        );
    };

    window._htIsDraft = function(id) {
        return typeof id === 'string' && id.indexOf('draft-') === 0;
    };

    window._htIsDraftEdge = function(edgeData) {
        return !!(
            edgeData
            && (
                edgeData.draft_edge
                || (typeof edgeData.id === 'string' && edgeData.id.indexOf('draft-edge-') === 0)
            )
        );
    };

    window._htHasPersistedConnection = function(cy, sourceId, targetId) {
        return cy.edges().toArray().some(function(existingEdge) {
            var existingData = existingEdge.data();
            if (window._htIsDraftEdge(existingData)) return false;
            var edgeSource = existingData.source;
            var edgeTarget = existingData.target;
            return (
                (edgeSource === sourceId && edgeTarget === targetId)
                || (edgeSource === targetId && edgeTarget === sourceId)
            );
        });
    };

    window._htDraftId = window._htDraftId || function() {
        return 'draft-' + crypto.randomUUID();
    };

    window._htBuildDraftNode = function(opts) {
        var escapedName = window._htEscapeHtml(opts.name || '');
        var escapedType = window._htEscapeHtml(opts.type || '');
        return {
            data: {
                id: opts.id,
                label: escapedName,
                raw_name: opts.name || '',
                shape: opts.shape || 'rectangle',
                device_type: escapedType,
                raw_device_type: opts.type || '',
                status: 'Active',
                ip: window._htEscapeHtml(opts.ip || ''),
                mac: window._htEscapeHtml(opts.mac || ''),
                os: window._htEscapeHtml(opts.os || ''),
                notes: window._htEscapeHtml(opts.notes || ''),
                draft: true,
                draft_name: opts.name || '',
                draft_type: opts.type || '',
                draft_ip: opts.ip || '',
                draft_mac: opts.mac || '',
                draft_os: opts.os || '',
                draft_notes: opts.notes || ''
            },
            position: { x: opts.x || 200, y: opts.y || 200 },
            classes: 'draft'
        };
    };

    window._htUpdateDraftData = function(node, fields) {
        if (!node || !node.length) return;
        if (fields.name !== undefined) {
            node.data('draft_name', fields.name);
            node.data('raw_name', fields.name);
            node.data('label', window._htEscapeHtml(fields.name));
        }
        if (fields.type !== undefined) {
            node.data('draft_type', fields.type);
            node.data('raw_device_type', fields.type);
            node.data('device_type', window._htEscapeHtml(fields.type));
        }
        if (fields.ip !== undefined) {
            node.data('draft_ip', fields.ip);
            node.data('ip', window._htEscapeHtml(fields.ip));
        }
        if (fields.mac !== undefined) {
            node.data('draft_mac', fields.mac);
            node.data('mac', window._htEscapeHtml(fields.mac));
        }
        if (fields.os !== undefined) {
            node.data('draft_os', fields.os);
            node.data('os', window._htEscapeHtml(fields.os));
        }
        if (fields.notes !== undefined) {
            node.data('draft_notes', fields.notes);
            node.data('notes', window._htEscapeHtml(fields.notes));
        }
    };

    window._htDraftCount = function() {
        return window._cy ? window._cy.nodes('.draft').length : 0;
    };

    if (typeof window._htHasUnsavedChanges === 'undefined') {
        window._htHasUnsavedChanges = false;
    }

    window._htSetDraftStatus = function(hasUnsavedChanges) {
        window._htHasUnsavedChanges = !!hasUnsavedChanges;
        if (window._htUpdateDraftBadge) {
            window._htUpdateDraftBadge();
        }
    };

    window._htUpdateDraftBadge = function() {
        var hasUnsavedChanges = window._htHasUnsavedChanges === true;
        var badge = document.getElementById('ht-draft-badge');
        if (!badge) return;
        if (hasUnsavedChanges) {
            badge.textContent = 'Draft';
            badge.style.display = 'inline';
        } else {
            badge.style.display = 'none';
        }
    };

    window._htUpdateDraftBadge();
})();
"""
