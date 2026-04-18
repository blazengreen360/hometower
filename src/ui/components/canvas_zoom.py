"""Canvas zoom controls component — floating zoom/fit button group (HT-040).

Injects a pure-JS/HTML overlay into the canvas container.
No API changes — purely frontend.
"""
import json

from nicegui import ui

from src.ui.components.device_type_options import get_creatable_device_types

_BTN_STYLE = (
    "width:44px;height:44px;border-radius:var(--ht-radius-input);"
    "background:var(--ht-bg-surface-raised);"
    "border:1px solid var(--ht-border);"
    "color:var(--ht-text-primary);"
    "cursor:pointer;font-size:1.25rem;line-height:1;"
    "padding:0;display:flex;align-items:center;justify-content:center;"
    "transition:background var(--ht-transition-fast);"
)

_HELP_DEVICE_TYPES_JS = json.dumps(
    [device_type.value for device_type in get_creatable_device_types()]
)

_ZOOM_CONTROLS_JS = (
    """
(function() {
    if (window._htZoomControlsLoaded) return;
    window._htZoomControlsLoaded = true;
    var helpDeviceTypes = __HT_HELP_DEVICE_TYPES__;

    function closeHelpModal() {
        var existing = document.getElementById('ht-help-overlay');
        if (existing) existing.remove();
    }

    function createToolCard(deviceType) {
        var card = document.createElement('div');
        card.style.cssText = [
            'display:flex',
            'align-items:center',
            'justify-content:center',
            'padding:6px 10px',
            'border-radius:var(--ht-radius-input)',
            'background:var(--ht-bg-surface-raised)',
            'border:1px solid var(--ht-border)',
            'cursor:grab',
            'font-size:0.78rem',
            'color:var(--ht-text-primary)',
            'user-select:none'
        ].join(';');
        card.setAttribute('draggable', 'true');
        card.innerText = deviceType;
        card.addEventListener('dragstart', function(e) {
            e.dataTransfer.setData('deviceType', deviceType);
            e.dataTransfer.effectAllowed = 'copy';
            closeHelpModal();
        });
        return card;
    }

    function openHelpModal() {
        if (document.getElementById('ht-help-overlay')) return;

        var overlay = document.createElement('div');
        overlay.id = 'ht-help-overlay';
        overlay.style.cssText = [
            'position:fixed',
            'top:0',
            'left:0',
            'right:0',
            'bottom:0',
            'z-index:12000',
            'background:color-mix(in srgb, var(--ht-bg-base) 68%, transparent)',
            'display:flex',
            'align-items:center',
            'justify-content:center'
        ].join(';');

        var modal = document.createElement('div');
        modal.style.cssText = [
            'width:min(680px, 92vw)',
            'max-height:84vh',
            'overflow:auto',
            'background:var(--ht-bg-surface-raised)',
            'border:1px solid var(--ht-border)',
            'border-radius:var(--ht-radius-modal)',
            'padding:14px'
        ].join(';');

        var head = document.createElement('div');
        head.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px;';
        var title = document.createElement('div');
        title.innerText = 'Topology Help';
        title.style.cssText = 'font-weight:700;font-size:0.95rem;color:var(--ht-text-primary);';
        var closeBtn = document.createElement('button');
        closeBtn.innerText = 'Close';
        closeBtn.style.cssText = [
            'padding:4px 10px',
            'border-radius:var(--ht-radius-input)',
            'border:1px solid var(--ht-border)',
            'background:var(--ht-bg-surface-raised)',
            'color:var(--ht-text-primary)',
            'cursor:pointer'
        ].join(';');
        closeBtn.addEventListener('click', closeHelpModal);
        head.appendChild(title);
        head.appendChild(closeBtn);

        var body = document.createElement('div');
        body.style.cssText = 'display:flex;flex-direction:column;gap:10px;color:var(--ht-text-secondary);font-size:0.82rem;';

        function paragraph(text) {
            var p = document.createElement('div');
            p.innerText = text;
            p.style.cssText = 'line-height:1.4;';
            return p;
        }

        var toolsHeader = document.createElement('div');
        toolsHeader.innerText = 'Device Tools (drag to canvas)';
        toolsHeader.style.cssText = 'font-weight:600;color:var(--ht-text-primary);margin-top:4px;';

        var toolsWrap = document.createElement('div');
        toolsWrap.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;';
        helpDeviceTypes.forEach(function(deviceType) {
            toolsWrap.appendChild(createToolCard(deviceType));
        });

        body.appendChild(paragraph('Drag a device tool onto the canvas to create a new node.'));
        body.appendChild(paragraph('Associations: Shift+click source device, then target device.'));
        body.appendChild(paragraph("Tip: right-click a node and choose 'Start Association'."));
        body.appendChild(paragraph('Delete actions always ask for confirmation before removing data.'));
        body.appendChild(toolsHeader);
        body.appendChild(toolsWrap);

        modal.appendChild(head);
        modal.appendChild(body);
        overlay.appendChild(modal);
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) closeHelpModal();
        });
        document.body.appendChild(overlay);
    }

    function buildControls(parent) {
        var wrap = document.createElement('div');
        wrap.id = 'ht-zoom-controls';
        wrap.style.cssText = 'position:absolute;bottom:16px;right:16px;z-index:100;display:flex;flex-direction:column;gap:4px;';

        function btn(id, html, title) {
            var b = document.createElement('button');
            b.id = id;
            b.title = title;
            b.setAttribute('aria-label', title);
            b.style.cssText = '"""
    + _BTN_STYLE
    + """';
            b.innerHTML = html;
            wrap.appendChild(b);
            return b;
        }

        btn('ht-zoom-in', '+', 'Zoom In');
        btn('ht-zoom-out', '&minus;', 'Zoom Out');
        btn(
            'ht-zoom-fit',
            '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">'
                + '<rect x="5" y="5" width="14" height="14" rx="2" ry="2" '
                + 'fill="none" stroke="currentColor" stroke-width="2"></rect>'
                + '<path d="M9 12h6M12 9v6" fill="none" stroke="currentColor" stroke-width="2" '
                + 'stroke-linecap="round"></path>'
            + '</svg>',
            'Fit to Screen'
        );
        btn('ht-help-open', '?', 'Help');
        parent.appendChild(wrap);

        document.getElementById('ht-help-open').addEventListener('click', openHelpModal);

        function waitCy(cb, n) {
            if (window._cy) { cb(); }
            else if ((n || 0) < 50) {
                setTimeout(function() { waitCy(cb, (n || 0) + 1); }, 100);
            }
        }

        waitCy(function() {
            var cy = window._cy;
            document.getElementById('ht-zoom-in').addEventListener('click', function() {
                var w = cy.width(), h = cy.height();
                cy.zoom({ level: cy.zoom() * 1.2, renderedPosition: { x: w / 2, y: h / 2 } });
            });
            document.getElementById('ht-zoom-out').addEventListener('click', function() {
                var w = cy.width(), h = cy.height();
                cy.zoom({ level: cy.zoom() / 1.2, renderedPosition: { x: w / 2, y: h / 2 } });
            });
            document.getElementById('ht-zoom-fit').addEventListener('click', function() {
                if (cy.elements().length > 0) { cy.fit(undefined, 40); }
            });
        });
    }

    function init(n) {
        var cyEl = document.getElementById('cy');
        if (cyEl) {
            buildControls(cyEl.parentElement);
        } else if ((n || 0) < 50) {
            setTimeout(function() { init((n || 0) + 1); }, 100);
        }
    }
    init();
})();
"""
).replace("__HT_HELP_DEVICE_TYPES__", _HELP_DEVICE_TYPES_JS)


def inject_zoom_controls() -> None:
    """Inject floating zoom/fit controls into the canvas container.

    Must be called after render_canvas() so the #cy element exists in the DOM.
    The button group is appended via JS to cy's parent (position: relative container).
    """
    ui.add_body_html(f"<script>{_ZOOM_CONTROLS_JS}</script>")
