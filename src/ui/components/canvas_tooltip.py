"""Cytoscape.js service tooltip — on-hover service list popup.

Extracted from canvas.py to keep both files under the 250-line limit.

Defines ``window._htInitTooltipHandlers`` which is called by ``initCanvas``
in canvas.py after the Cytoscape instance (``window._cy``) is created.
"""
from nicegui import ui

_CANVAS_TOOLTIP_JS = """
(function() {
    if (typeof window._htInitTooltipHandlers !== 'undefined') return;

    window._htInitTooltipHandlers = function() {
        var cy = window._cy;

        window._htServicesCache = {};

        cy.on('mouseover', 'node', function(evt) {
            var nodeId = evt.target.id();
            if (nodeId.indexOf('draft-') === 0) {
                window._htShowDraftTooltip(evt);
                return;
            }
            if (evt.target.hasClass('ghost') || evt.target.data('ghost') === true) {
                window._htShowGhostTooltip(evt, evt.target.data());
                return;
            }
            if (window._htServicesCache[nodeId] !== undefined) {
                window._htShowServiceTooltip(evt, window._htServicesCache[nodeId]);
                return;
            }
            fetch('/api/devices/' + nodeId + '?include=services', {
                credentials: 'include',
            })
            .then(function(r) { return r.ok ? r.json() : null; })
            .then(function(data) {
                window._htServicesCache[nodeId] = (data && data.services) ? data.services : [];
                window._htShowServiceTooltip(evt, window._htServicesCache[nodeId]);
            });
        });

        cy.on('mouseout', 'node', function() {
            var tip = document.getElementById('ht-svc-tooltip');
            if (tip) tip.remove();
        });
    };

    window._htShowDraftTooltip = function(evt) {
        var tip = document.getElementById('ht-svc-tooltip');
        if (tip) tip.remove();
        var s = getComputedStyle(document.documentElement);
        tip = document.createElement('div');
        tip.id = 'ht-svc-tooltip';
        tip.style.cssText = 'position:fixed;z-index:9000;background:' + s.getPropertyValue('--ht-bg-surface-raised').trim() + ';border-radius:var(--ht-radius-input);'
            + 'padding:8px 12px;font-size:0.8rem;color:' + s.getPropertyValue('--ht-text-primary').trim() + ';pointer-events:none;'
            + 'box-shadow:' + s.getPropertyValue('--ht-shadow-md').trim() + ';max-width:260px;';
        tip.style.left = (evt.originalEvent.clientX + 14) + 'px';
        tip.style.top  = (evt.originalEvent.clientY - 8) + 'px';
        var label = document.createElement('div');
        label.textContent = 'Unpublished draft — publish to save';
        label.style.cssText = 'font-style:italic;';
        tip.appendChild(label);
        document.body.appendChild(tip);
    };

    window._htShowGhostTooltip = function(evt, data) {
        var tip = document.getElementById('ht-svc-tooltip');
        if (tip) tip.remove();
        var s = getComputedStyle(document.documentElement);
        tip = document.createElement('div');
        tip.id = 'ht-svc-tooltip';
        tip.style.cssText = 'position:fixed;z-index:9000;background:' + s.getPropertyValue('--ht-bg-surface-raised').trim() + ';border-radius:var(--ht-radius-input);'
            + 'padding:8px 12px;font-size:0.8rem;color:' + s.getPropertyValue('--ht-text-primary').trim() + ';pointer-events:none;'
            + 'box-shadow:' + s.getPropertyValue('--ht-shadow-md').trim() + ';max-width:280px;';
        tip.style.left = (evt.originalEvent.clientX + 14) + 'px';
        tip.style.top  = (evt.originalEvent.clientY - 8) + 'px';
        var label = document.createElement('div');
        var name = (data && (data.ghost_original_name || data.raw_name || data.label)) || 'Deleted device';
        label.textContent = String(name).replace(' (Deleted from inventory)', '') + ' is deleted from inventory';
        label.style.cssText = 'color:' + s.getPropertyValue('--ht-warning').trim() + ';';
        tip.appendChild(label);
        document.body.appendChild(tip);
    };

    window._htShowServiceTooltip = function(evt, services) {
        var tip = document.getElementById('ht-svc-tooltip');
        if (tip) tip.remove();
        if (!services || services.length === 0) return;
        var s = getComputedStyle(document.documentElement);
        tip = document.createElement('div');
        tip.id = 'ht-svc-tooltip';
        tip.style.cssText = 'position:fixed;z-index:9000;background:' + s.getPropertyValue('--ht-bg-surface-raised').trim() + ';border-radius:var(--ht-radius-input);'
            + 'padding:8px 12px;font-size:0.8rem;color:' + s.getPropertyValue('--ht-text-primary').trim() + ';pointer-events:none;'
            + 'box-shadow:' + s.getPropertyValue('--ht-shadow-md').trim() + ';max-width:260px;';
        tip.style.left = (evt.originalEvent.clientX + 14) + 'px';
        tip.style.top  = (evt.originalEvent.clientY - 8) + 'px';
        var successColor = s.getPropertyValue('--ht-success').trim();
        var errorColor = s.getPropertyValue('--ht-error').trim();
        var mutedColor = s.getPropertyValue('--ht-text-secondary').trim();
        services.forEach(function(svc) {
            var row = document.createElement('div');
            row.style.cssText = 'display:flex;align-items:center;gap:6px;padding:2px 0;';
            var dot = document.createElement('span');
            var statusColors = { running: successColor, stopped: errorColor, unknown: mutedColor };
            var statusKey = String(svc.status || '').trim().toLowerCase();
            dot.style.cssText = 'width:8px;height:8px;border-radius:50%;flex-shrink:0;'
                + 'background:' + (statusColors[statusKey] || mutedColor) + ';';
            var label = document.createElement('span');
            label.textContent = svc.name + (svc.port ? ':' + svc.port : '');
            row.appendChild(dot);
            row.appendChild(label);
            tip.appendChild(row);
        });
        document.body.appendChild(tip);
    };
})();
"""


def inject_canvas_tooltip() -> None:
    """Inject the service tooltip IIFE into the page body."""
    ui.add_body_html(f"<script>{_CANVAS_TOOLTIP_JS}</script>")
