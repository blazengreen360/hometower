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
        var isDraft = window._htIsDraft && window._htIsDraft(d.id);
        var isGhost = !!(node && node.hasClass('ghost')) || !!(d.data && d.data.ghost === true);

        if (isGhost) return;

        var actions = [
            { label: 'Start Association',       event: 'ht:association-source' },
            { label: 'Duplicate',               event: 'ht:node-duplicate',           hide: isDraft },
            { label: 'Convert to Container',    event: 'ht:node-convert-container',   hide: isContainer || isDraft },
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
            item.style.cssText = 'padding:8px 16px;color:var(--ht-text-primary);cursor:pointer;font-size:0.875rem;transition:background var(--ht-transition-fast);';
            item.onmouseenter = function() { item.style.background = 'var(--ht-accent-glow)'; };
            item.onmouseleave = function() { item.style.background = ''; };
            item.onclick = function() {
                document.dispatchEvent(new CustomEvent(action.event, { detail: d }));
                menu.remove();
            };
            menu.appendChild(item);
        });

        document.body.appendChild(menu);
        // Position near cursor — use last pointer event
        var x = window._htLastCtxX || 200, y = window._htLastCtxY || 200;
        menu.style.left = x + 'px';
        menu.style.top  = y + 'px';

        var dismiss = function() { menu.remove(); document.removeEventListener('click', dismiss); };
        setTimeout(function() { document.addEventListener('click', dismiss); }, 10);
    });

    document.addEventListener('mousemove', function(e) {
        window._htLastCtxX = e.clientX;
        window._htLastCtxY = e.clientY;
    });
})();
"""
