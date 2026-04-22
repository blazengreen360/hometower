"""Context menu IIFE for the topology canvas (HT-051 extraction).

Self-contained — injected into page body via <script> tag.
"""

CONTEXT_MENU_JS: str = """
(function() {
    if (window._htContextMenuInit) return;
    window._htContextMenuInit = true;
    document.addEventListener('ht:context-menu-request', function(evt) {
        if (window.HT_READONLY) return;
        var d = evt.detail;
        var existing = document.getElementById('ht-ctx-menu');
        if (existing) existing.remove();

        var menu = document.createElement('div');
        menu.id = 'ht-ctx-menu';
        menu.style.cssText = [
            'position:fixed', 'z-index:9999',
            'background:var(--ht-bg-surface-raised)', 'border-radius:var(--ht-radius-card)',
            'padding:4px 0', 'min-width:140px',
            'box-shadow:var(--ht-shadow-md)',
        ].join(';');

        var node = window._cy ? window._cy.getElementById(d.id) : null;
        var isContainer = node && (node.hasClass('container') || node.isParent());
        var hasParent = !!(node && node.data && node.data('parent'));
        var isDraft = window._htIsDraft && window._htIsDraft(d.id);
        var isGhost = !!(node && node.hasClass('ghost')) || !!(d.data && d.data.ghost === true);

        if (isGhost) return;

        var actions = [
            { label: 'Start Association',       event: 'ht:association-source' },
            { label: 'Remove from container',   event: 'ht:node-remove-from-container', hide: !hasParent },
            { label: 'Duplicate',               event: 'ht:node-duplicate',           hide: isDraft },
            { label: 'Convert to Container',    event: 'ht:node-convert-container',   hide: isContainer },
            { label: 'Convert to Node',         event: 'ht:node-unconvert-container', hide: !isContainer || isDraft },
            { label: 'Collapse/Expand',         event: 'ht:node-collapse-toggle',     hide: !isContainer || isDraft },
            { label: 'Publish to Inventory',    event: 'ht:node-publish',             hide: !isDraft },
            { label: 'Delete Draft',            event: 'ht:node-delete',              hide: !isDraft },
            { label: 'Remove from View',        event: 'ht:node-remove-from-view',    hide: isDraft },
        ];
        actions.forEach(function(action) {
            if (action.hide) return;
            var item = document.createElement('div');
            item.innerText = action.label;
            item.style.cssText = 'display:flex;align-items:center;min-height:32px;width:100%;box-sizing:border-box;padding:8px 16px;color:var(--ht-text-primary);cursor:pointer;font-size:0.875rem;transition:background var(--ht-transition-fast);';
            item.onmouseenter = function() { item.style.background = 'var(--ht-accent-glow)'; };
            item.onmouseleave = function() { item.style.background = ''; };
            item.onclick = function() {
                document.dispatchEvent(new CustomEvent(action.event, { detail: d }));
                menu.remove();
            };
            menu.appendChild(item);
        });

        document.body.appendChild(menu);
        // Position near cursor; prefer precise coordinates from event detail.
        var x = Number(d && d.clientX);
        var y = Number(d && d.clientY);
        if (!Number.isFinite(x) || !Number.isFinite(y)) {
            x = Number(window._htLastCtxX);
            y = Number(window._htLastCtxY);
        }
        if (!Number.isFinite(x)) x = 200;
        if (!Number.isFinite(y)) y = 200;
        var viewportWidth = window.innerWidth || document.documentElement.clientWidth;
        var viewportHeight = window.innerHeight || document.documentElement.clientHeight;
        var menuWidth = menu.offsetWidth || 160;
        var menuHeight = menu.offsetHeight || 32;
        var clampedX = Math.max(0, Math.min(x, viewportWidth - menuWidth - 4));
        var clampedY = Math.max(0, Math.min(y, viewportHeight - menuHeight - 4));
        menu.style.left = clampedX + 'px';
        menu.style.top  = clampedY + 'px';

        var dismiss = function() { menu.remove(); document.removeEventListener('click', dismiss); };
        setTimeout(function() { document.addEventListener('click', dismiss); }, 10);
    });

    document.addEventListener('mousemove', function(e) {
        window._htLastCtxX = e.clientX;
        window._htLastCtxY = e.clientY;
    });
})();
"""
